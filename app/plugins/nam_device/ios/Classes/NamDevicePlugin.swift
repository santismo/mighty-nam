import Flutter
import UIKit
import CoreAudioKit
import Security
public final class NamDevicePlugin: NSObject, FlutterPlugin {
    private let midi = NamMidi()
    private weak var presenter: UIViewController?
    public static func register(with registrar: FlutterPluginRegistrar) {
        let instance = NamDevicePlugin()
        registrar.addMethodCallDelegate(instance, channel: FlutterMethodChannel(name:"nam_plug/device",binaryMessenger:registrar.messenger()))
    }
    public func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        do {
            switch call.method {
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
            case "loadLibrary": result(UserDefaults.standard.string(forKey:"nam-plug-library-v1"))
            case "saveLibrary":
                guard let value=call.arguments as? String,value.utf8.count<=131072 else { result(FlutterError(code:"size",message:"Preset library is too large",details:nil)); return }
                UserDefaults.standard.set(value,forKey:"nam-plug-library-v1");result(nil)
            case "devices": result(try midi.devices())
            case "inspect":
                guard let args=call.arguments as? [String:Any], let id=args["source"] as? Int else { result(FlutterError(code:"arguments",message:"Select a device",details:nil)); return }
                midi.inspect(id) { value in
                    switch value { case .success(let data): result(data)
                    case .failure(let error): result(FlutterError(code:"connection",message:String(describing:error),details:nil)) }
                }
            case "disconnect": midi.disconnect(); result(nil)
            case "bluetooth":
                guard let view=UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).flatMap({ $0.windows }).first(where: { $0.isKeyWindow })?.rootViewController, view.presentedViewController == nil else { result(FlutterError(code:"busy",message:"Close the current dialog first",details:nil)); return }
                presenter=view
                let controller=CABTMIDICentralViewController(); controller.navigationItem.rightBarButtonItem=UIBarButtonItem(barButtonSystemItem:.done,target:self,action:#selector(closeBluetooth))
                view.present(UINavigationController(rootViewController:controller),animated:true); result(nil)
            default: result(FlutterMethodNotImplemented)
            }
        } catch { result(FlutterError(code:"connection",message:String(describing:error),details:nil)) }
    }
    @objc private func closeBluetooth(){ presenter?.dismiss(animated:true) }
}
