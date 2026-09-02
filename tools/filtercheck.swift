// Replicates Skim's SKColorEffectFilters dark-mode chain and reports the sRGB
// values that pure white and pure black map to. Lets us verify the color math
// numerically instead of eyeballing a screenshot.
//
//   swift filtercheck.swift                 -> baseline (upstream constants)
//   swift filtercheck.swift RRGGBB RRGGBB   -> solve F/bias for <bg> <text> targets
import Foundation
import CoreImage
import AppKit

let LR = 0.2126, LG = 0.7152, LB = 0.0722

func srgbToLinear(_ c: Double) -> Double {
    c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4)
}
func hexToLinear(_ hex: String) -> (Double, Double, Double) {
    var v: UInt64 = 0
    Scanner(string: hex).scanHexInt64(&v)
    return (srgbToLinear(Double((v >> 16) & 0xff) / 255.0),
            srgbToLinear(Double((v >> 8) & 0xff) / 255.0),
            srgbToLinear(Double(v & 0xff) / 255.0))
}

// Applies gamma 0.625 -> CIColorMatrix -> gamma 1.6 to a 2x1 white/black image
// and returns the resulting sRGB byte triples.
func runChain(f: (Double, Double, Double), bias: (Double, Double, Double)) -> [[UInt8]] {
    var px: [UInt8] = [255, 255, 255, 255, 0, 0, 0, 255]
    let src = px.withUnsafeMutableBytes {
        CIImage(bitmapData: Data($0), bytesPerRow: 8, size: CGSize(width: 2, height: 1),
                format: .RGBA8, colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!)
    }
    let g1 = CIFilter(name: "CIGammaAdjust", parameters: [kCIInputImageKey: src, "inputPower": 0.625])!
    let m = CIFilter(name: "CIColorMatrix", parameters: [
        kCIInputImageKey: g1.outputImage!,
        "inputRVector": CIVector(x: 1.0 - LR * f.0, y: -LG * f.0, z: -LB * f.0, w: 0),
        "inputGVector": CIVector(x: -LR * f.1, y: 1.0 - LG * f.1, z: -LB * f.1, w: 0),
        "inputBVector": CIVector(x: -LR * f.2, y: -LG * f.2, z: 1.0 - LB * f.2, w: 0),
        "inputAVector": CIVector(x: 0, y: 0, z: 0, w: 1),
        "inputBiasVector": CIVector(x: bias.0, y: bias.1, z: bias.2, w: 0)])!
    let g2 = CIFilter(name: "CIGammaAdjust", parameters: [kCIInputImageKey: m.outputImage!, "inputPower": 1.6])!

    let ctx = CIContext(options: [.workingColorSpace: CGColorSpace(name: CGColorSpace.linearSRGB)!,
                                  .outputColorSpace: CGColorSpace(name: CGColorSpace.sRGB)!])
    var out = [UInt8](repeating: 0, count: 8)
    out.withUnsafeMutableBytes {
        ctx.render(g2.outputImage!, toBitmap: $0.baseAddress!, rowBytes: 8,
                   bounds: CGRect(x: 0, y: 0, width: 2, height: 1), format: .RGBA8,
                   colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!)
    }
    return [Array(out[0..<3]), Array(out[4..<7])]
}

func hex(_ c: [UInt8]) -> String { String(format: "#%02X%02X%02X", c[0], c[1], c[2]) }

let args = CommandLine.arguments
if args.count >= 3 {
    // Solve: bias = text in "u" space; F = 1 + text_u - bg_u  (per channel)
    let bg = hexToLinear(args[1]), tx = hexToLinear(args[2])
    let u = { (x: Double) in pow(x, 1.0 / 1.6) }
    let bu = (u(bg.0), u(bg.1), u(bg.2)), tu = (u(tx.0), u(tx.1), u(tx.2))
    let f = (1.0 + tu.0 - bu.0, 1.0 + tu.1 - bu.1, 1.0 + tu.2 - bu.2)
    print(String(format: "f      = %.4f %.4f %.4f", f.0, f.1, f.2))
    print(String(format: "bias   = %.4f %.4f %.4f", tu.0, tu.1, tu.2))
    let r = runChain(f: f, bias: tu)
    print("branco -> \(hex(r[0]))   (alvo #\(args[1].uppercased()))")
    print("preto  -> \(hex(r[1]))   (alvo #\(args[2].uppercased()))")
} else {
    let f = 1.8972
    let r = runChain(f: (f, f, f), bias: (1.0, 1.0, 1.0))
    print("BASELINE upstream (f=\(f), bias=1,1,1)")
    print("branco -> \(hex(r[0]))   (comentario do codigo promete 45/255 = #2D2D2D)")
    print("preto  -> \(hex(r[1]))")
}
