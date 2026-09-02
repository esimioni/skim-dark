// Renders page 1 of a PDF through Skim's inverted-dark-mode filter chain
// (CIGammaAdjust 0.625 -> CIColorMatrix -> CIGammaAdjust 1.6), the way the
// app's layer contentFilters do, so "how it looks" can be produced and measured
// without a screen capture. Same math as the patch: white lands on B, black on
// b, f = 1 + b - B per channel.
//
//   swiftc -O -o renderpage renderpage.swift
//   renderpage <in.pdf> <out.png> <bgGray 0-1> [textHex]   (no textHex = white text)
//
// Prints the control first: a pure white and a pure black pixel through the
// same function, so the render is checked against the intended landing colors.
import Foundation
import AppKit
import PDFKit
import CoreImage

let LR = 0.2126, LG = 0.7152, LB = 0.0722
func toLinear(_ c: Double) -> Double { c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4) }
func hexRGB(_ hex: String) -> [Double] {
    var v: UInt64 = 0; Scanner(string: hex).scanHexInt64(&v)
    return [Double((v >> 16) & 0xff) / 255.0, Double((v >> 8) & 0xff) / 255.0, Double(v & 0xff) / 255.0]
}
let srgb = CGColorSpace(name: CGColorSpace.sRGB)!

func chain(_ input: CIImage, f: [Double], b: [Double]) -> CIImage {
    let g1 = CIFilter(name: "CIGammaAdjust", parameters: [kCIInputImageKey: input, "inputPower": 0.625])!
    let m = CIFilter(name: "CIColorMatrix", parameters: [
        kCIInputImageKey: g1.outputImage!,
        "inputRVector": CIVector(x: 1.0 - LR * f[0], y: -LG * f[0], z: -LB * f[0], w: 0),
        "inputGVector": CIVector(x: -LR * f[1], y: 1.0 - LG * f[1], z: -LB * f[1], w: 0),
        "inputBVector": CIVector(x: -LR * f[2], y: -LG * f[2], z: 1.0 - LB * f[2], w: 0),
        "inputAVector": CIVector(x: 0, y: 0, z: 0, w: 1),
        "inputBiasVector": CIVector(x: b[0], y: b[1], z: b[2], w: 0)])!
    return CIFilter(name: "CIGammaAdjust", parameters: [kCIInputImageKey: m.outputImage!, "inputPower": 1.6])!.outputImage!
}
let ctx = CIContext(options: [.workingColorSpace: CGColorSpace(name: CGColorSpace.linearSRGB)!, .outputColorSpace: srgb])

let a = CommandLine.arguments
let B = pow(toLinear(Double(a[3])!), 0.625)
let b = a.count > 4 ? hexRGB(a[4]).map { pow(toLinear($0), 0.625) } : [1.0, 1.0, 1.0]
let f = b.map { 1.0 + $0 - B }

// control: white and black through the same chain
var px: [UInt8] = [255, 255, 255, 255, 0, 0, 0, 255]
let swatch = px.withUnsafeMutableBytes { CIImage(bitmapData: Data($0), bytesPerRow: 8, size: CGSize(width: 2, height: 1), format: .RGBA8, colorSpace: srgb) }
var out = [UInt8](repeating: 0, count: 8)
out.withUnsafeMutableBytes { ctx.render(chain(swatch, f: f, b: b), toBitmap: $0.baseAddress!, rowBytes: 8, bounds: CGRect(x: 0, y: 0, width: 2, height: 1), format: .RGBA8, colorSpace: srgb) }
print(String(format: "control: white -> #%02X%02X%02X, black -> #%02X%02X%02X", out[0], out[1], out[2], out[4], out[5], out[6]))

// the page, at 2x, white background, drawn by PDFKit
let doc = PDFDocument(url: URL(fileURLWithPath: a[1]))!   // kept alive: a page whose document is gone draws nothing
let page = doc.page(at: 0)!
let box = page.bounds(for: .mediaBox)
let scale = 2.0, w = Int(box.width * scale), h = Int(box.height * scale)
let cg = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4, space: srgb, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
cg.setFillColor(CGColor(colorSpace: srgb, components: [1, 1, 1, 1])!)
cg.fill(CGRect(x: 0, y: 0, width: w, height: h))
cg.scaleBy(x: scale, y: scale)
cg.translateBy(x: -box.origin.x, y: -box.origin.y)
page.draw(with: .mediaBox, to: cg)
let rendered = chain(CIImage(cgImage: cg.makeImage()!), f: f, b: b)
let result = ctx.createCGImage(rendered, from: CGRect(x: 0, y: 0, width: w, height: h), format: .RGBA8, colorSpace: srgb)!
let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: a[2]) as CFURL, "public.png" as CFString, 1, nil)!
CGImageDestinationAddImage(dest, result, nil)
CGImageDestinationFinalize(dest)
print("wrote \(a[2]) \(w)x\(h)")
