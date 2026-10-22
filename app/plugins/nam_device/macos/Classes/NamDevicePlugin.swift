import FlutterMacOS
import AppKit
import Security
public final class NamDevicePlugin: NSObject, FlutterPlugin {
    private let midi = NamMidi()
    private let toneBrowser = ToneBrowserWindow()
    public static func register(with registrar: FlutterPluginRegistrar) {
        let instance = NamDevicePlugin()
        registrar.addMethodCallDelegate(instance, channel: FlutterMethodChannel(name:"nam_plug/device",binaryMessenger:registrar.messenger))
    }
    public func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        do {
            switch call.method {
            case "openToneBrowser":
                guard let url = call.arguments as? String else {result(nil);return}
                toneBrowser.open(url,result:result)
            case "nextToneSelection": toneBrowser.next(result)
            case "toneBrowserStatus": toneBrowser.status(call.arguments as? String ?? "");result(nil)
            case "loadToneSession", "saveToneSession":
                guard let args=call.arguments as? [String:Any], let client=args["clientId"] as? String,
                      client.hasPrefix("t3k_pub_"), client.utf8.count<=256 else {
                    result(FlutterError(code:"session",message:"Invalid public client",details:nil));return
                }
                let query:[String:Any]=[kSecClass as String:kSecClassGenericPassword,
                    kSecAttrService as String:"org.namplug.controller.tone3000",
                    kSecAttrAccount as String:client]
                if call.method == "loadToneSession" {
                    var lookup=query;lookup[kSecReturnData as String]=true;lookup[kSecMatchLimit as String]=kSecMatchLimitOne
                    var data:CFTypeRef?;let status=SecItemCopyMatching(lookup as CFDictionary,&data)
                    if status == errSecItemNotFound {result(nil);return}
                    guard status == errSecSuccess,let bytes=data as? Data,bytes.count<=16384 else {
                        result(FlutterError(code:"session",message:"Could not read saved sign-in",details:nil));return
                    }
                    result(String(data:bytes,encoding:.utf8));return
                }
                guard let text=args["value"] as? String else {
                    let status=SecItemDelete(query as CFDictionary)
                    if status == errSecSuccess || status == errSecItemNotFound {result(nil)} else {
                        result(FlutterError(code:"session",message:"Could not remove saved sign-in",details:nil))
                    };return
                }
                guard let bytes=text.data(using:.utf8),bytes.count<=16384 else {
                    result(FlutterError(code:"session",message:"Sign-in data too large",details:nil));return
                }
                var status=SecItemUpdate(query as CFDictionary,[kSecValueData as String:bytes] as CFDictionary)
                if status == errSecItemNotFound {
                    var item=query;item[kSecValueData as String]=bytes
                    item[kSecAttrAccessible as String]=kSecAttrAccessibleWhenUnlockedThisDeviceOnly
                    status=SecItemAdd(item as CFDictionary,nil)
                }
                if status == errSecSuccess {result(nil)} else {
                    result(FlutterError(code:"session",message:"Could not securely save sign-in",details:nil))
                }
            case "loadLibrary": result(UserDefaults.standard.string(forKey:"nam-plug-library-v2"))
            case "saveLibrary":
                guard let value=call.arguments as? String,value.utf8.count<=2097152 else { result(FlutterError(code:"size",message:"Preset library is too large",details:nil)); return }
                UserDefaults.standard.set(value,forKey:"nam-plug-library-v2");result(nil)
            case "devices": result(try midi.devices())
            case "inspect":
                guard let args=call.arguments as? [String:Any], let id=args["source"] as? Int else { result(FlutterError(code:"arguments",message:"Select a device",details:nil)); return }
                midi.inspect(id) { value in
                    switch value { case .success(let data): result(data)
                    case .failure(let error): result(FlutterError(code:"connection",message:String(describing:error),details:nil)) }
                }
            case "readStockControls", "applyStockControls", "setCabinetBypassed":
                guard let args=call.arguments as? [String:Any],let id=args["source"] as? Int else {
                    result(FlutterError(code:"arguments",message:"Select a plug",details:nil));return
                }
                var plan: NamStockWire.Plan?
                if call.method == "setCabinetBypassed" {
                    guard let bypassed=args["bypassed"] as? Bool else {
                        result(FlutterError(code:"arguments",message:"Choose a cabinet bypass state",details:nil));return
                    }
                    plan=NamStockWire.Plan(cabinetBypassed:bypassed)
                }
                if call.method == "applyStockControls" {
                    guard args["namEnabled"] == nil || args["namEnabled"] is Bool else {
                        result(FlutterError(code:"arguments",message:"Invalid NAM bypass control",details:nil));return
                    }
                    guard let controls=args["controls"] as? [[Int]],let order=args["order"] as? [Int],
                          let checked=NamStockWire.Plan(controls:controls,order:order,namEnabled:args["namEnabled"] as? Bool) else {
                        result(FlutterError(code:"arguments",message:"These controls are not supported by this firmware",details:nil));return
                    }
                    plan=checked
                }
                midi.stock(id,plan:plan) { value in
                    switch value { case .success(let data): result(data)
                    case .failure(let error): result(FlutterError(code:"connection",message:String(describing:error),details:nil)) }
                }
            case "setOutputBuffer":
                guard let args=call.arguments as? [String:Any],let id=args["source"] as? Int,
                      let samples=args["samples"] as? Int else {
                    result(FlutterError(code:"arguments",message:"Select a plug and output buffer",details:nil));return
                }
                midi.outputBuffer(id,samples:samples) { value in
                    switch value { case .success(let data): result(data)
                    case .failure(let error): result(FlutterError(code:"connection",message:String(describing:error),details:nil)) }
                }
            case "setListening":
                guard let args=call.arguments as? [String:Any],let id=args["source"] as? Int,
                      let enabled=args["enabled"] as? Bool else {
                    result(FlutterError(code:"arguments",message:"Select a plug and listening state",details:nil));return
                }
                midi.listen(id,enabled:enabled) { value in
                    switch value { case .success(let data): result(data)
                    case .failure(let error): result(FlutterError(code:"connection",message:String(describing:error),details:nil)) }
                }
            case "exchangeModelFrame", "exchangePresetFrame", "exchangeFxFrame":
                guard let args=call.arguments as? [String:Any],let id=args["source"] as? Int,
                      let frame=args["frame"] as? FlutterStandardTypedData else {
                    result(FlutterError(code:"arguments",message:"Select a device and model frame",details:nil));return
                }
                let exchange = call.method == "exchangeFxFrame" ? midi.fx : (call.method == "exchangePresetFrame" ? midi.preset : midi.exchange)
                exchange(id, Array(frame.data)) { value in
                    switch value {
                    case .success(let data):
                        guard let raw=data["frame"] as? [UInt8] else {
                            result(FlutterError(code:"protocol",message:"Missing model reply",details:nil));return
                        }
                        result(FlutterStandardTypedData(bytes:Data(raw)))
                    case .failure(let error):
                        result(FlutterError(code:"connection",message:String(describing:error),details:nil))
                    }
                }
            case "tunerFrame":
                guard let args=call.arguments as? [String:Any],let id=args["source"] as? Int,
                      let op=args["operation"] as? Int,let page=args["page"] as? Int,let nonce=args["nonce"] as? Int else {
                    result(FlutterError(code:"arguments",message:"Invalid tuner request",details:nil));return
                }
                midi.tuner(id,operation:op,page:page,nonce:nonce) { value in
                    switch value {
                    case .success(let data):
                        guard let raw=data["frame"] as? [UInt8] else {
                            result(FlutterError(code:"protocol",message:"Missing tuner reply",details:nil));return
                        }
                        result(FlutterStandardTypedData(bytes:Data(raw)))
                    case .failure(let error):result(FlutterError(code:"connection",message:String(describing:error),details:nil))
                    }
                }
            case "disconnect": midi.disconnect(); result(nil)
            case "bluetooth":
                result(FlutterError(code:"bluetooth",message:"Pair Bluetooth MIDI in Audio MIDI Setup, then refresh. USB is ready directly.",details:nil))
            default: result(FlutterMethodNotImplemented)
            }
        } catch { result(FlutterError(code:"connection",message:String(describing:error),details:nil)) }
    }
}

import AppKit
import WebKit
import FlutterMacOS

// No JavaScript bridge, token injection or media playback. Cookies stay in WebKit.
final class ToneBrowserWindow: NSObject, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate {
    private var window: NSWindow?
    private var web: WKWebView?
    private var pending: FlutterResult?
    private var queued: String?
    private var state = ""
    private let label = NSTextField(labelWithString: "TONE3000")
    func open(_ text: String, result: @escaping FlutterResult) {
        guard let url = URL(string: text), url.scheme == "https", url.host == "www.tone3000.com",
              url.path == "/api/v1/oauth/authorize", let parts = URLComponents(url:url,resolvingAgainstBaseURL:false),
              let token = parts.queryItems?.first(where:{$0.name == "state"})?.value,
              parts.queryItems?.first(where:{$0.name == "redirect_uri"})?.value == "mighty-nam://oauth/callback" else {
            result(FlutterError(code:"browser",message:"Invalid TONE3000 address",details:nil));return
        }
        pending?(nil); pending = result; queued = nil; state = token
        if window == nil {
            let config = WKWebViewConfiguration(); config.websiteDataStore = .default()
            config.mediaTypesRequiringUserActionForPlayback = .all
            let view = WKWebView(frame:.zero, configuration:config)
            view.navigationDelegate = self; view.uiDelegate = self; view.allowsBackForwardNavigationGestures = true
            // Extra defense against preview autoplay; the OAuth URL also requests preview=false.
            let rules = "[{\"trigger\":{\"url-filter\":\".*\",\"resource-type\":[\"media\"]},\"action\":{\"type\":\"block\"}}]"
            WKContentRuleListStore.default().compileContentRuleList(forIdentifier:"mighty-nam-no-media",encodedContentRuleList:rules) { list,_ in
                if let list = list { config.userContentController.add(list) }
            }
            let w = NSWindow(contentRect:NSRect(x:0,y:0,width:1060,height:760),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
            w.title = "TONE3000 · mighty-nam"; w.isReleasedWhenClosed = false; w.delegate = self
            let stack = NSStackView(views:[label,view]); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 10
            stack.edgeInsets = NSEdgeInsets(top:12,left:12,bottom:12,right:12)
            view.translatesAutoresizingMaskIntoConstraints = false
            view.widthAnchor.constraint(equalTo:stack.widthAnchor,constant:-24).isActive = true
            w.contentView = stack; w.center(); window = w; web = view
        }
        label.stringValue = "Choose a capture"; window?.makeKeyAndOrderFront(nil); web?.load(URLRequest(url:url))
    }
    func next(_ result: @escaping FlutterResult) {
        guard window != nil else {result(nil);return}
        if let value = queued {queued = nil;result(value);return}
        pending?(nil);pending = result
    }
    func status(_ value: String) { label.stringValue = String(value.prefix(180)) }
    func windowWillClose(_ notification: Notification) { pending?(nil);pending = nil;queued = nil;window = nil;web = nil }
    private func handle(_ url: URL, trusted: Bool) -> Bool {
        guard url.scheme == "mighty-nam" else {return false}
        guard trusted, url.host == "oauth", url.path == "/callback", url.fragment == nil,
              let items = URLComponents(url:url,resolvingAgainstBaseURL:false)?.queryItems,
              items.filter({$0.name == "state"}).count == 1,
              items.first(where:{$0.name == "state"})?.value == state else {return true}
        if let done = pending {pending = nil;done(url.absoluteString)} else if queued == nil {queued = url.absoluteString}
        // Cancel the redirect, not the window: catalog/history/scroll remain intact.
        return true
    }
    func webView(_ view: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy)->Void) {
        guard let url = action.request.url else {decisionHandler(.cancel);return}
        let origin = action.sourceFrame.securityOrigin
        if handle(url,trusted:origin.protocol == "https" && origin.host == "www.tone3000.com") {decisionHandler(.cancel);return}
        guard url.scheme == "https", ["www.tone3000.com","tone3000.com"].contains(url.host ?? "") else {decisionHandler(.cancel);return}
        decisionHandler(.allow)
    }
    func webView(_ view: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures)->WKWebView? {
        if let url = action.request.url, url.scheme == "https", url.host == "www.tone3000.com" {view.load(URLRequest(url:url))};return nil
    }
}
