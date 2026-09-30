Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

$text = @"
Fitness training requires both exercise and recovery.
Protein provides amino acids needed for tissue maintenance and muscle protein synthesis.
Carbohydrates can support training and replenish muscle glycogen.
Sleep and recovery are important for managing fatigue.
"@

$synth.SetOutputToWaveFile("data\uploads\video_audio.wav")
$synth.Speak($text)
$synth.Dispose()

Write-Host "Audio for test video created."