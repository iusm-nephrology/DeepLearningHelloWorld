import os
import json
import argparse
import torch
import data_loader.data_loaders as module_data
import data_loader.augmenters as module_augmentation
import model.loss as module_loss
import model.metric as module_metric
import model.model as module_arch
from trainer import Trainer
from utils import Logger
from utils import util
from utils import torchsummary
from utils import viewTraining
from utils import lr_finder
import importlib
import math
import torchvision
print("Modules loaded")

def get_instance(module, name, config, *args):
    return getattr(module, config[name]['type'])(*args, **config[name]['args'])

def visualize(dataloader):
    images, labels = next(iter(dataloader))
    fig = plt.figure(figsize=(40, 40))
    batch = math.ceil(math.sqrt(dataloader.batch_size))
    for i in range(len(images)):
        a = fig.add_subplot(batch,batch,i+1)
        img = images[i].permute(1,2,0).numpy()
        img = np.squeeze(img)
        imgplot = plt.imshow(img, cmap = "gray")
        plt.axis('off')
        a.set_title("Label = " +str(labels[i].numpy()), fontsize=30)

def main(config, resume):
    print("================")
    print("Beginning Training")
    train_logger = Logger()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # setup data_loader instances
    augmentation = get_instance(module_augmentation, 'augmenter', config)
    data_loader = get_instance(module_data, 'data_loader', config)
    data_loader.transforms = augmentation.transforms
    data_loader.dataset.transforms = data_loader.apply_transforms()
    valid_data_loader = data_loader.split_validation()

    # build model architecture
    model = get_instance(module_arch, 'arch', config)
    print(model)
    
    if torch.cuda.is_available():
        print("Using GPU: " + torch.cuda.get_device_name(0))
    else:
        print("Using CPU to train")
        
    # get function handles of loss and metrics
    loss = getattr(module_loss, config['loss']) #looks in model/loss.py for criterion function specified in config
    criterion = loss(data_loader.dataset.weight.to(device)) # for imbalanced datasets
    metrics = [getattr(module_metric, met) for met in config['metrics']]

    # build optimizer, learning rate scheduler. delete every lines containing lr_scheduler for disabling scheduler
    trainable_params = filter(lambda p: p.requires_grad, model.parameters())
    optimizer = get_instance(torch.optim, 'optimizer', config, trainable_params)
    lr_scheduler = get_instance(torch.optim.lr_scheduler, 'lr_scheduler', config, optimizer)

    trainer = Trainer(model, criterion, metrics, optimizer,
                      resume=resume,
                      config=config,
                      data_loader=data_loader,
                      valid_data_loader=valid_data_loader,
                      lr_scheduler=lr_scheduler,
                      train_logger=train_logger)

    trainer.train()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PyTorch Template')
    parser.add_argument('-c', '--config', default=None, type=str,
                        help='config file path (default: None)')
    parser.add_argument('-r', '--resume', default=None, type=str,
                        help='path to latest checkpoint (default: None)')
    parser.add_argument('-d', '--device', default=None, type=str,
                        help='indices of GPUs to enable (default: all)')
    args = parser.parse_args()

    if args.config:
        # load config file
        with open(args.config) as handle:
            config = json.load(handle)
        # setting path to save trained models and log files
        path = os.path.join(config['trainer']['save_dir'], config['name'])

    elif args.resume:
        # load config from checkpoint if new config file is not given.
        # Use '--config' and '--resume' together to fine-tune trained model with changed configurations.
        config = torch.load(args.resume)['config']
        
    else:
        raise AssertionError("Configuration file need to be specified. Add '-c config.json', for example.")

    if args.device:
        os.environ["CUDA_VISIBLE_DEVICES"] = args.device

    main(config, args.resume)