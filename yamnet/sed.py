print('Loading TensorFlow...')
import numpy as np
#import scipy.signal
import soundfile as sf
import tensorflow as tf

 

print('Loading YAMNet...')
import params as yamnet_params
import yamnet as yamnet_model
params = yamnet_params.Params()
yamnet = yamnet_model.yamnet_frames_model(params)
yamnet.load_weights('yamnet.h5')
yamnet_classes = yamnet_model.class_names('yamnet_class_map.csv')

 

import os, pyaudio, time,math
#os.system('jack_control start')
p = pyaudio.PyAudio()
os.system('clear')
#print('Sound Event Detection by running inference on every 1.024 second audio stream from the microphone!\n')

 

CHUNK = 1024 # frames_per_buffer # samples per chunk
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 1.024                                          # need at least 975 ms
INFERENCE_WINDOW = 2 * int(RATE / CHUNK * RECORD_SECONDS)       # 2 * 16 CHUNKs
THRESHOLD = 0.4

 

def calVolumeDB(waveData, frameSize, overLap):
    wlen = len(waveData)
    step = frameSize - overLap
    frameNum = int(math.ceil(wlen*1.0/step))
    volume = np.zeros((frameNum,1))
    for i in range(frameNum):
        curFrame = waveData[np.arange(i*step,min(i*step+frameSize,wlen))]
        curFrame = curFrame - np.mean(curFrame) # zero-justified
        volume[i] = 10*np.log10(np.sum(curFrame*curFrame))
    return volume

 

stream = p.open(format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK)

 

CHUNKs = []
with open('sed.npy', 'ab') as f:
    while True:
        try:
            stream.start_stream()
            for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                data = stream.read(CHUNK)
                CHUNKs.append(data)
                # print(len(CHUNKs))
            stream.stop_stream()

 

            if len(CHUNKs) > INFERENCE_WINDOW:
                CHUNKs = CHUNKs[int(RATE / CHUNK * RECORD_SECONDS):]
                # print('new len: ',len(CHUNKs))
            wav_data = np.frombuffer(b''.join(CHUNKs), dtype=np.int16)
            waveform = wav_data / tf.int16.max#32768.0
            waveform = waveform.astype('float32')
            scores, embeddings, spectrogram = yamnet(waveform)
            prediction = np.mean(scores[:-1], axis=0) # last one scores comes from insufficient samples
            # assert (prediction==scores[0]).numpy().all() # only one scores at RECORD_SECONDS = 1.024
            volume12 = calVolumeDB(wav_data,256,128)

            assert len(scores[:-1]) == CHUNK * len(CHUNKs) / RATE // 0.48 - 1 # hop 0.48 seconds
            top5 = np.argsort(prediction)[::-1][:5]
            print(time.ctime().split()[3],
                ''.join((f" {prediction[i]:.0%} ---> {yamnet_classes[i]} |  volume---> {round(volume12.mean(),2)} db" if prediction[i] >= THRESHOLD else '') for i in top5))
            np.save(f, np.concatenate(([time.time()], prediction)))
            ##prediction[i]:.2f ///   {:.0%}".format(prediction[i])
            #(f" {prediction[i]:.2f} ---> {yamnet_classes[i]}" 
        except:
            stream.stop_stream()
            stream.close()
            p.terminate()
            f.close()
