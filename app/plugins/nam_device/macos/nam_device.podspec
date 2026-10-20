Pod::Spec.new do |s|
  s.name = 'nam_device'
  s.version = '0.2.0'
  s.summary = 'NAM Plug MIDI controller transport'
  s.description = 'Identified diagnostics and bounded RAM model transfers over system MIDI.'
  s.homepage = 'https://example.invalid/nam-plug'
  s.license = { :type => 'MIT', :file => '../LICENSE' }
  s.author = { 'NAM Plug contributors' => '' }
  s.source = { :path => '.' }
  s.source_files = 'Classes/**/*'
  s.dependency 'FlutterMacOS'
  s.platform = :osx, '10.15'
  s.swift_version = '5.0'
  s.frameworks = 'CoreMIDI', 'Security'
end
