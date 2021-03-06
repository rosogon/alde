#
# Copyright 2018 Atos Research and Innovation
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# https://www.gnu.org/licenses/agpl-3.0.txt
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
# 
# This is being developed for the TANGO Project: http://tango-project.eu
#
# Module that reads the json file containing GPU model numbers
#

import json
from models import GPU

GPU_FILE = "gpu_cards_list.json"

FIELD_CODE_SLURM="model_code_slurm"
FIELD_MODEL_NAME="model_name"

def find_gpu(model_code: str, field):
    """
    This function will look at the internal json gpu inventory and look
    for the GPU that has the same value of the given field as model_code 
    and return a GPU object
    """

    with open(GPU_FILE) as data_file:
        gpus = json.load(data_file)

    gpu = next((gpu for gpu in gpus if gpu[field] == model_code), None)

    if gpu:
        return GPU(vendor_id=gpu['vendor_id'], model_name=gpu['model_name'])
    else:
        return None


def find_gpu_slurm(model_code_slurm : str): 
    return find_gpu(model_code_slurm, FIELD_CODE_SLURM)