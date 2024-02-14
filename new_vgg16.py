# -*- coding: utf-8 -*-
"""New_VGG16.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1icnv53yGfv0qZpjWo8HQ7IywiT9O4gFz
"""

from google.colab import drive
drive.mount('/content/drive', force_remount=True)

!cp -r "/content/drive/MyDrive/Dataset" "/content/"

!pip install datasets

!pip install transformers

!pip install --upgrade transformers

!pip install timm

import os
import torch
import torchvision
import numpy as np
import matplotlib.pyplot as plt
from torchvision.datasets import ImageFolder
from torchvision.transforms import (ToTensor, Resize, RandomResizedCrop, RandomRotation,
                                   RandomHorizontalFlip, RandomVerticalFlip, ColorJitter)
from sklearn.model_selection import KFold
from torch.utils.data import DataLoader, random_split, Subset
from torch import nn, optim
from torch.optim.lr_scheduler import StepLR
from sklearn.metrics import precision_recall_fscore_support

!cp -r "/content/drive/MyDrive/combined_dataset" "/content/combined_dataset"


# Path to your dataset
data_dir = '/content/drive/MyDrive/combined_dataset'

# Parameters
image_size = (224, 224)
batch_size = 32
num_epochs = 10
num_folds = 10

# Transforms
train_transform = torchvision.transforms.Compose([
    RandomResizedCrop(image_size),
    RandomRotation(15),
    RandomHorizontalFlip(),
    RandomVerticalFlip(),
    ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
    ToTensor()
])

val_test_transform = torchvision.transforms.Compose([
    Resize(image_size, antialias=True),
    ToTensor()
])

# Loading the full dataset with train transform
full_dataset = ImageFolder(data_dir, transform=train_transform)
num_classes = len(full_dataset.classes)

# Splitting the dataset into training, validation, and test sets (let's say 70%, 15%, 15%)
train_size = int(0.7 * len(full_dataset))
validation_size = (len(full_dataset) - train_size) // 2
test_size = len(full_dataset) - train_size - validation_size
train_dataset, validation_dataset, test_dataset = torch.utils.data.random_split(full_dataset, [train_size, validation_size, test_size])

# Apply the validation and test transforms to the respective splits
validation_dataset.dataset.transform = val_test_transform
test_dataset.dataset.transform = val_test_transform

# Data loaders
train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
val_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
num_classes = len(full_dataset.classes)

kfold = KFold(n_splits=num_folds, shuffle=True)
fold_results = []

for fold, (train_ids, _) in enumerate(kfold.split(train_dataset)):
    print(f"FOLD {fold + 1}")

    train_subsampler = Subset(train_dataset, train_ids)
    train_loader = DataLoader(train_subsampler, batch_size=batch_size, shuffle=True)

    # Using VGG-16 with Dropout
    model = torchvision.models.vgg16(pretrained=True)
    model.classifier[2] = nn.Dropout(0.5) # Adding dropout to the default VGG classifier
    model.classifier[6] = torch.nn.Linear(model.classifier[6].in_features, num_classes)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0001, weight_decay=0.0001)
    scheduler = StepLR(optimizer, step_size=5, gamma=0.1) # example values for step_size and gamma

    model.to(device)

    train_acc_list, val_acc_list, train_loss_list, val_loss_list = [], [], [], []
    train_prec_list, train_recall_list, train_f1_list = [], [], []
    val_prec_list, val_recall_list, val_f1_list = [], [], []

    for epoch in range(num_epochs):
        # Training
        model.train()
        train_loss, train_correct = 0.0, 0
        all_labels, all_preds = [], []
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = nn.CrossEntropyLoss()(outputs, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            preds = torch.argmax(outputs, dim=1)
            train_correct += (preds == labels).sum().item()
            all_labels.extend(labels.cpu().numpy())
            all_preds.extend(preds.cpu().numpy())
        scheduler.step()

        avg_train_loss = train_loss / len(train_loader.dataset)
        avg_train_accuracy = train_correct / len(train_loader.dataset)
        train_precision, train_recall, train_f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='weighted', zero_division=1)

        # Validation
        model.eval()
        val_loss, val_correct = 0.0, 0
        all_labels, all_preds = [], []
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = nn.CrossEntropyLoss()(outputs, labels)
                val_loss += loss.item()
                preds = torch.argmax(outputs, dim=1)
                val_correct += (preds == labels).sum().item()
                all_labels.extend(labels.cpu().numpy())
                all_preds.extend(preds.cpu().numpy())

        avg_val_loss = val_loss / len(val_loader.dataset)
        avg_val_accuracy = val_correct / len(val_loader.dataset)
        val_precision, val_recall, val_f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='weighted', zero_division=1)

        print(f"Epoch [{epoch+1}/{num_epochs}] Training Loss: {avg_train_loss:.4f}, Training Accuracy: {avg_train_accuracy:.4f}, Training Precision: {train_precision:.4f}, Training Recall: {train_recall:.4f}, Training F1: {train_f1:.4f}, Validation Loss: {avg_val_loss:.4f}, Validation Accuracy: {avg_val_accuracy:.4f}, Validation Precision: {val_precision:.4f}, Validation Recall: {val_recall:.4f}, Validation F1: {val_f1:.4f}")

        train_acc_list.append(avg_train_accuracy)
        val_acc_list.append(avg_val_accuracy)
        train_loss_list.append(avg_train_loss)
        val_loss_list.append(avg_val_loss)
        train_prec_list.append(train_precision)
        train_recall_list.append(train_recall)
        train_f1_list.append(train_f1)
        val_prec_list.append(val_precision)
        val_recall_list.append(val_recall)
        val_f1_list.append(val_f1)

    fold_results.append({
        'train_acc': train_acc_list,
        'val_acc': val_acc_list,
        'train_loss': train_loss_list,
        'val_loss': val_loss_list,
        'train_prec': train_prec_list,
        'val_prec': val_prec_list,
        'train_recall': train_recall_list,
        'val_recall': val_recall_list,
        'train_f1': train_f1_list,
        'val_f1': val_f1_list
    })

# Compute averages over all folds
avg_train_acc = np.mean([result['train_acc'] for result in fold_results], axis=0)
avg_val_acc = np.mean([result['val_acc'] for result in fold_results], axis=0)
avg_train_loss = np.mean([result['train_loss'] for result in fold_results], axis=0)
avg_val_loss = np.mean([result['val_loss'] for result in fold_results], axis=0)
avg_train_prec = np.mean([result['train_prec'] for result in fold_results], axis=0)
avg_val_prec = np.mean([result['val_prec'] for result in fold_results], axis=0)
avg_train_recall = np.mean([result['train_recall'] for result in fold_results], axis=0)
avg_val_recall = np.mean([result['val_recall'] for result in fold_results], axis=0)
avg_train_f1 = np.mean([result['train_f1'] for result in fold_results], axis=0)
avg_val_f1 = np.mean([result['val_f1'] for result in fold_results], axis=0)

# Plotting the average metrics
plt.figure(figsize=(20, 4))

plt.subplot(1, 4, 1)
plt.plot(range(num_epochs), avg_train_acc, label='Training')
plt.plot(range(num_epochs), avg_val_acc, label='Validation')
plt.xlabel('Epochs')
plt.ylabel('Accuracy')
plt.legend()

plt.subplot(1, 4, 2)
plt.plot(range(num_epochs), avg_train_loss, label='Training')
plt.plot(range(num_epochs), avg_val_loss, label='Validation')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.legend()

plt.subplot(1, 4, 3)
plt.plot(range(num_epochs), avg_train_prec, label='Training')
plt.plot(range(num_epochs), avg_val_prec, label='Validation')
plt.xlabel('Epochs')
plt.ylabel('Precision')
plt.legend()

plt.subplot(1, 4, 4)
plt.plot(range(num_epochs), avg_train_recall, label='Training')
plt.plot(range(num_epochs), avg_val_recall, label='Validation')
plt.xlabel('Epochs')
plt.ylabel('Recall')
plt.legend()

plt.tight_layout()
plt.show()



"""import matplotlib.pyplot as plt

# Initialize lists to store values
train_losses = []
train_accuracies = []
test_losses = []
test_accuracies = []

# Train the model
for epoch in range(num_epochs):
    train_loss = 0.0
    train_correct = 0
    
    # Training code...

    # Calculate train accuracy and append to list
    train_accuracy = train_correct / len(train_dataset)
    train_accuracies.append(train_accuracy)

    # Evaluate on the test set
    model.eval()
    test_loss = 0.0
    test_correct = 0
    
    # Testing code...
    
    # Calculate test accuracy and append to list
    test_accuracy = test_correct / len(test_dataset)
    test_accuracies.append(test_accuracy)

    # Append train and test losses to lists
    train_losses.append(train_loss)
    test_losses.append(test_loss)

# Plotting the tables
epochs = range(1, num_epochs + 1)

# Plot train and test losses
plt.plot(epochs, train_losses, label='Train Loss')
plt.plot(epochs, test_losses, label='Test Loss')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.title('Training and Test Loss')
plt.legend()
plt.show()

# Plot train and test accuracies
plt.plot(epochs, train_accuracies, label='Train Accuracy')
plt.plot(epochs, test_accuracies, label='Test Accuracy')
plt.xlabel('Epochs')
plt.ylabel('Accuracy')
plt.title('Training and Test Accuracy')
plt.legend()
plt.show()

"""