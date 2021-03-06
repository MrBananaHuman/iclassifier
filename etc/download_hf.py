from __future__ import absolute_import, division, print_function

import sys
import os
import argparse
import time
import pdb
import logging

from transformers import AutoTokenizer, AutoConfig, AutoModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--model_name_or_path", type=str, default='bert-base-cased',
                        help="Path to pre-trained model or shortcut name(ex, bert-base-cased)")
    parser.add_argument("--do_lower_case", action="store_true",
                        help="Set this flag if you are using an uncased model.")

    opt = parser.parse_args()

    # download
    logger.info("[Downloading transformers...]")
    tokenizer = AutoTokenizer.from_pretrained(opt.model_name_or_path,
                                          do_lower_case=opt.do_lower_case)
    model = AutoModel.from_pretrained(opt.model_name_or_path,
                                  from_tf=bool(".ckpt" in opt.model_name_or_path))
    config = model.config
    logger.info("[Done]")
    # save
    output_dir = opt.model_name_or_path
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    tokenizer.save_pretrained(output_dir)
    model.save_pretrained(output_dir)
    logger.info("[Saved to {}]".format(output_dir))
 
if __name__ == '__main__':
    main()
