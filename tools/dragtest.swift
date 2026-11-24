// dragtest — a real mouse drag (CGEvent) from a point on Skim's window to a window
// of this process, which takes file drops and reports what it got: the source's
// operation mask, the file dropped and its size, and the app in front at the drop.
// usage: dragtest <startX> <startY> <window-name-prefix> <log>
//        (global top-left coordinates, in points)
// Lock: drags only when the window under the start point is Skim's and its name
// starts with the prefix (the test document), never another one. Run by
// tools/sendcheck.sh, which compiles it; the mouse goes back where it was.
import Cocoa

let args = CommandLine.arguments
guard args.count == 5, let startX = Double(args[1]), let startY = Double(args[2]) else {
    print("usage: dragtest <startX> <startY> <window-name-prefix> <log>")
    exit(64)
}
let start = CGPoint(x: startX, y: startY)
let namePrefix = args[3]
let logPath = args[4]
var lines: [String] = []
func log(_ s: String) { lines.append(s); print(s); fflush(stdout) }
func finish(_ code: Int32) {
    try? lines.joined(separator: "\n").write(toFile: logPath, atomically: true, encoding: .utf8)
    exit(code)
}
func front() -> String { NSWorkspace.shared.frontmostApplication?.localizedName ?? "?" }

class DropView: NSView {
    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {
        log("entered: source mask=\(sender.draggingSourceOperationMask.rawValue)")
        return .copy
    }
    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        let urls = sender.draggingPasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL] ?? []
        for u in urls {
            let size = (try? FileManager.default.attributesOfItem(atPath: u.path)[.size] as? Int) ?? -1
            log("dropped: \(u.path) size=\(size)")
        }
        log("front at drop: \(front())")
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { finish(urls.isEmpty ? 1 : 0) }
        return true
    }
}

func windowUnder(_ p: CGPoint) -> (owner: String, name: String) {
    let info = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    for w in info {
        guard (w[kCGWindowLayer as String] as? Int) == 0, let b = w[kCGWindowBounds as String] as? [String: Double] else { continue }
        if CGRect(x: b["X"]!, y: b["Y"]!, width: b["Width"]!, height: b["Height"]!).contains(p) {
            return (w[kCGWindowOwnerName as String] as? String ?? "?", w[kCGWindowName as String] as? String ?? "")
        }
    }
    return ("none", "")
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let screenHeight = NSScreen.screens[0].frame.height
// content at top-left (900, 300), 400 x 300
let window = NSWindow(contentRect: NSRect(x: 900, y: screenHeight - 600, width: 400, height: 300), styleMask: [.titled], backing: .buffered, defer: false)
window.title = "drop target"
let dropView = DropView(frame: NSRect(x: 0, y: 0, width: 400, height: 300))
dropView.registerForDraggedTypes([.fileURL])
window.contentView = dropView
window.level = .floating
window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)

DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
    let under = windowUnder(start)
    log("under start: \(under.owner) / \(under.name)")
    log("front before drag: \(front())")
    guard under.owner == "Skim", under.name.hasPrefix(namePrefix) else {
        log("ABORT: the start point is not on the test document's window")
        finish(2)
        return
    }
    let original = CGEvent(source: nil)?.location ?? start
    let end = CGPoint(x: 1100, y: 450)
    DispatchQueue.global().async {
        func post(_ type: CGEventType, _ p: CGPoint) {
            CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
        }
        post(.mouseMoved, start); usleep(150_000)
        post(.leftMouseDown, start); usleep(150_000)
        for i in 1...30 {
            let t = Double(i) / 30.0
            post(.leftMouseDragged, CGPoint(x: start.x + (end.x - start.x) * t, y: start.y + (end.y - start.y) * t))
            usleep(25_000)
        }
        usleep(300_000)
        post(.leftMouseUp, end); usleep(200_000)
        post(.mouseMoved, original)
        DispatchQueue.main.asyncAfter(deadline: .now() + 4.0) { log("no drop within 4 s"); finish(1) }
    }
}
app.run()