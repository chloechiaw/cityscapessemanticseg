import torch
import os
import numpy as np
import scipy.misc as m
from torch.utils import data
import torch.nn as nn
import sklearn.metrics as skm
import torch.optim as optim
from tqdm import tqdm
import torch.nn.functional as F
import time
from PIL import Image
import torchvision
from glob import glob
import torch.nn as nn
from tqdm import tqdm
import matplotlib.pyplot as plt
import torchvision.transforms as transform
from torch.utils.data import DataLoader,Dataset
from torch.utils.tensorboard import SummaryWriter
from torchvision.utils import make_grid

from google.colab import drive
drive.mount('/content/gdrive')

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/gdrive/MyDrive/cityscapes/train

train_path = '/content/gdrive/MyDrive/cityscapes/train'
valid_path = '/content/gdrive/MyDrive/cityscapes/val'

import os
# Define the base directory path

# Get a list of all .jpg files in the directory
image_files = [f for f in os.listdir(train_path) if f.endswith('.jpg')]

# Generate file paths to the images using os.path.join()
image_paths = [os.path.join(train_path, f) for f in image_files]

print(image_paths)

train_dataset = []
validation_dataset = []

from torch.utils.data import DataLoader,Dataset

import os

class MyDataset(Dataset):
    
    def __init__(self, images_path ,transform_img=None ,transform_label=None):
        
        self.dir_path = images_path
        self.images_path = os.listdir(images_path)
        self.transform_img = transform_img
        self.transform_label = transform_label

    def __len__(self):
        return len(self.images_path)

    def __getitem__(self, idx):
        img = plt.imread(os.path.join(self.dir_path, self.images_path[idx]))
        image,label = img[:,:int(img.shape[1]/2)],img[:,int(img.shape[1]/2):]
    
        if self.transform_img:
            image = self.transform_img(image)
            
        if self.transform_label:
            label = self.transform_label(label)
            
        return image, label

import torchvision.transforms as transform

mytransformsImage = transform.Compose(
    [
        transform.ToTensor(),
        #transform.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        transform.RandomHorizontalFlip(p=0.9)
    ]
)

mytransformsLabel = transform.Compose(
    [
        transform.ToTensor(),
    ]
)

# train dataset
traindata = MyDataset(train_path, mytransformsImage, mytransformsLabel)
# val dataset
valdata = MyDataset(valid_path, mytransformsImage, mytransformsLabel)

# Creating the DataLoaders
batch_size = 4
train_loader = DataLoader(traindata,batch_size)
vaild_loader = DataLoader(valdata,1)

import torch.nn as nn

class Convblock(nn.Module):
    
      def __init__(self,input_channel,output_channel,kernal=3,stride=1,padding=1):
            
        super().__init__()
        self.convblock = nn.Sequential(
            nn.Conv2d(input_channel,output_channel,kernal,stride,padding),
            nn.BatchNorm2d(output_channel),
            nn.ReLU(inplace=True),
            nn.Conv2d(output_channel,output_channel,kernal),
            nn.ReLU(inplace=True),
        )
    

      def forward(self,x):
        x = self.convblock(x)
        return x

class UNet(nn.Module):
    
    def __init__(self,input_channel,retain=True):

        super().__init__()

        self.conv1 = Convblock(input_channel,32)
        self.conv2 = Convblock(32,64)
        self.conv3 = Convblock(64,128)
        self.conv4 = Convblock(128,256)
        self.neck = nn.Conv2d(256,512,3,1)
        self.upconv4 = nn.ConvTranspose2d(512,256,3,2,0,1)
        self.dconv4 = Convblock(512,256)
        self.upconv3 = nn.ConvTranspose2d(256,128,3,2,0,1)
        self.dconv3 = Convblock(256,128)
        self.upconv2 = nn.ConvTranspose2d(128,64,3,2,0,1)
        self.dconv2 = Convblock(128,64)
        self.upconv1 = nn.ConvTranspose2d(64,32,3,2,0,1)
        self.dconv1 = Convblock(64,32)
        self.out = nn.Conv2d(32,3,1,1)
        self.retain = retain
        
    def forward(self,x):
        
     
        conv1 = self.conv1(x)
        pool1 = F.max_pool2d(conv1,kernel_size=2,stride=2)
       
        conv2 = self.conv2(pool1)
        pool2 = F.max_pool2d(conv2,kernel_size=2,stride=2)
   
        conv3 = self.conv3(pool2)
        pool3 = F.max_pool2d(conv3,kernel_size=2,stride=2)

        conv4 = self.conv4(pool3)
        pool4 = F.max_pool2d(conv4,kernel_size=2,stride=2)

       
        neck = self.neck(pool4)
        
    
        

        upconv4 = self.upconv4(neck)
        croped = self.crop(conv4,upconv4)

        dconv4 = self.dconv4(torch.cat([upconv4,croped],1))
   
        upconv3 = self.upconv3(dconv4)
        croped = self.crop(conv3,upconv3)
     
        dconv3 = self.dconv3(torch.cat([upconv3,croped],1))

        upconv2 = self.upconv2(dconv3)
        croped = self.crop(conv2,upconv2)

        dconv2 = self.dconv2(torch.cat([upconv2,croped],1))

        upconv1 = self.upconv1(dconv2)
        croped = self.crop(conv1,upconv1)

        dconv1 = self.dconv1(torch.cat([upconv1,croped],1))
        out = self.out(dconv1)
        
        if self.retain == True:
            out = F.interpolate(out,list(x.shape)[2:])

        return out
    
    def crop(self,input_tensor,target_tensor):
        _,_,H,W = target_tensor.shape
        return transform.CenterCrop([H,W])(input_tensor)

import torch

device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = UNet(3).float().to(device)

lr = 0.01
epochs = 30

lossfunc = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=lr)

train_acc = []
val_acc = []
train_loss = []
val_loss = []

from tqdm import tqdm
import matplotlib.pyplot as plt

for i in range(epochs):
    
    trainloss = 0
    valloss = 0
    
    for img, label in tqdm(train_loader):
        '''
            Traning the Model.
        '''

        optimizer.zero_grad()
        img = img.to(device)
        label = label.to(device)
        output = model(img)
        loss = lossfunc(output,label)
        loss.backward()
        optimizer.step()
        trainloss+=loss.item()
    
    if(i%5==0):
        show(img,output,label)

    train_loss.append(trainloss/len(train_loader))    
  
    for img,label in tqdm(vaild_loader):
        '''
            Validation of Model.
        '''
        img = img.to(device)
        label = label.to(device)
        output = model(img)
        loss = lossfunc(output,label)
        valloss+=loss.item()
        
    val_loss.append(valloss/len(vaild_loader))  
    
    print("epoch : {} ,train loss : {} ,valid loss : {} ".format(i,train_loss[-1],val_loss[-1]))
