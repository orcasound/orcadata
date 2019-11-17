import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from lib.acoustic_model import AcousticModel
import lib.dataset as dataset
from lib.opt import optimize
import lib.media as media
import matplotlib.pyplot as plt
import numpy as np
import collections

    
def pYHatGivenWhale(yhat_i, i, isWhale, histograms):
    hist, binEdges = histograms[i][isWhale]
    binIdx = sum([e < yhat_i for e in binEdges])-1
    return hist[binIdx]
    
def makeTwoHistograms(i, yHats, data, windowSize, fs, stride):
    yHat_i_whale = []
    yHat_i_noWhale = []
    j = 0
    while j < (len(data.data) - windowSize*fs)//stride:
        s = j*stride  # Sample index
        isWhale = data.labels[s:(s + windowSize*fs)]
        if isWhale:
            yHat_i_whale.append(yHats[j + i][0])
        else:
            yHat_i_noWhale.append(yHats[j + i][0])
        j += 1
    
    # These plots show the distributions of yHat probabilities
    # for both classes of event (whale and no whale)
#     plt.hist(yHat_i_noWhale,bins=50)
#     plt.show()
#     plt.hist(yHat_i_whale,bins=50)
#     plt.show()
    
    whaleHist = np.histogram(yHat_i_whale, bins=50, range=(0,1))
    paddedWhaleHist = whaleHist[0] + 1e-6 # Avoid dividing by zero
    whaleHist = (paddedWhaleHist/sum(paddedWhaleHist), whaleHist[1])
    
    noWhaleHist = np.histogram(yHat_i_noWhale, bins=50, range=(0,1))
    paddedNoWhaleHist = noWhaleHist[0] + 1e-6 # Avoid dividing by zero
    noWhaleHist = (paddedNoWhaleHist/sum(paddedNoWhaleHist), noWhaleHist[1])
    
    return whaleHist, noWhaleHist

def makeHistograms(yHats, data, windowSize, fs, stride):
    # Make two histograms for every i
    i = 0  # The window has many samples. Which one do we want to plot?
    histograms = collections.defaultdict(dict)
    for i in range(0, int((windowSize*fs/stride))+1):
        histWithWhale, histWithNoWhale = makeTwoHistograms(i, yHats, data, windowSize, fs, stride)
        histograms[i][True] = histWithWhale
        histograms[i][False] = histWithNoWhale
    
    return histograms

def probWhaleInWindow(isWhale, yHats, pWhaleBaseline, histograms):
    logSum = np.log(pWhaleBaseline)
    for i, yhat_i in enumerate(yHats):
        logSum += np.log(pYHatGivenWhale(yhat_i, i, isWhale, histograms))
    
    return logSum

def naiveBayes(yHats, pWhaleBaseline, histograms):
    "Returns 1 if there's a whale, else 0"
    probWhale = probWhaleInWindow(True, yHats, pWhaleBaseline, histograms)
    probNoWhale = probWhaleInWindow(False, yHats, (1-pWhaleBaseline), histograms)
    if probWhale > probNoWhale:
        return 1
    else:
        return 0
    
# def predictChunks(yHats, data, window, fs, stride, pWhaleBaseline):
#     numYHatsPerWindow = int(window*fs/stride)
#     histograms = makeHistograms(yHats, data, window, fs, stride)
#     chunkedPredictions = []

#     j = 0
#     while j < len(yHats)-numYHatsPerWindow:  # j indexes yHats
#         prediction = naiveBayes(yHats[j:j+numYHatsPerWindow], pWhaleBaseline, histograms)
#         chunkedPredictions += [prediction]*numYHatsPerWindow
#         j += numYHatsPerWindow

#     # Buffer the last <2 seconds
#     chunkedPredictions += [0]*(len(yHats)-len(chunkedPredictions))
    
#     return chunkedPredictions
    
def plot(trainYHats, trainData, testY, testYHats, window, fs, stride, pWhaleBaseline):
#     chunkedPredictions = predictChunks(yHats, data, window, fs, stride, pWhaleBaseline)
    naiveBayes = NaiveBayes(window, fs, stride)
    naiveBayes.train(trainYHats, trainData)
    chunkedPredictions = naiveBayes.predictChunks(testYHats, pWhaleBaseline)
    
    plt.figure(figsize=(30,500))
    plt.imshow(np.hstack((testY,testYHats,np.array([[x] for x in chunkedPredictions]))))
    plt.show()
    
class NaiveBayes:
    """ Use a Naive Bayes classifier (https://en.wikipedia.org/wiki/Naive_Bayes_classifier)
    to combine instantaneous predictions into a prediction over an entire window.
    Input: Predictions of the probability of an event (e.g. a whale call) for n contiguous time points
    Output: A prediction (0 or 1) of whether the event occurred during this window
    
    Sample usage (Training on "train", testing on "test", labelling two-second windows):
    fs=44100
    stride=8192
    pWhaleBaseline=0.1
    window=2
    plot(yhat_train, train_set, y_test, yhat_test, window, fs, stride, pWhaleBaseline)
    
    Future Work:
    - pWhale baseline is currently an input to the model. Ideally, this could either be learned
    from the training set (need to address class balance), or set as a hyperparameter to address
    sensitivity.
    - Currently, each p(yHat_i | isWhale) is estimated separately. However, it's fair to assume
    that they have the same distribution for all i. Consider estimating one distribution for all i.
    - Clearly, we have violated the independence assumption of Naive Bayes. This should get worse
    as the yHats are predicted at a smaller discretization. Look into ways to mitigate this problem
    (e.g. some sort of kernel? What happens as discretization goes to zero? Does pWhale matter less?)
    """
    def __init__(self, window, fs, stride):
        self.window = window
        self.fs = fs
        self.stride = stride
        self.histograms = None
    
    def train(self, yHats, data):
        self.histograms = makeHistograms(yHats, data, self.window, self.fs, self.stride)
        
    def predictWindow(self, yHats, pWhaleBaseline):
        if not self.histograms:
            raise Exception("please train first")
            
        return naiveBayes(yHats, pWhaleBaseline, self.histograms)
    
    def predictChunks(self, yHats, pWhaleBaseline):
        numYHatsPerWindow = int(self.window*self.fs/self.stride)
        chunkedPredictions = []

        j = 0
        while j < len(yHats)-numYHatsPerWindow:  # j indexes yHats
            prediction = self.predictWindow(yHats[j:j+numYHatsPerWindow], pWhaleBaseline)
            chunkedPredictions += [prediction]*numYHatsPerWindow
            j += numYHatsPerWindow

        # Buffer the last <2 seconds
        chunkedPredictions += [0]*(len(yHats)-len(chunkedPredictions))

        return chunkedPredictions

        
    
# def test():
#     fs=44100
#     stride=8192
#     pWhaleBaseline=0.1
#     window=2
#     yHats = yhat_train
#     data = largestride_test_set
#     plot(yHats, data, window, fs, stride, pWhaleBaseline)
    