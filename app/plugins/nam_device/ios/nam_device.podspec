Pod::Spec.new do |s|
  s.name = 'nam_device'
  s.version = '0.1.0'
  s.summary = 'mighty-nam MIDI controller transport'
  s.description = 'Read-only identified diagnostics over system USB or Bluetooth MIDI.'
  s.homepage = 'https://github.com/santismo/mighty-nam'
  s.license = { :type => 'MIT', :file => '../LICENSE' }
  s.author = { 'mighty-nam contributors' => '' }
  s.source = { :path => '.' }
  s.source_files = 'Classes/**/*'
  s.dependency 'Flutter'
  s.platform = :ios, '13.0'
  s.swift_version = '5.0'
  s.frameworks = 'CoreMIDI', 'CoreAudioKit'
end
