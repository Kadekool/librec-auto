import argparse
from librec_auto import read_config_file
from librec_auto.util import Status
import webbrowser

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use('Agg')  # For non-windowed plotting

viz_file_pattern_bar = "viz-bar-{}.png"
viz_file_pattern_box = "viz-box-{}.png"
viz_html_filename = "viz.html"
exp_dir_pattern = "exp[0-9][0-9][0-9]"

#This is slack library
import sys
import slack as sl
from slacker import Slacker

#This is dropbox library
import dropbox
import sys, os

#This is decrypted function
from cryptography.fernet import Fernet

'''
Zijun:
    Arg: 
    1). message: information wants to put into the slack 
    2). slack_api: slack group channel api key
    3). channel: which channel wants to put 
'''
def slack_send_message(message, slack_api, channel):
    slack = Slacker(str(slack_api))
    slack.chat.post_message(channel, message)

#Zijun: This is function for auto send file and comments to slack
''''
Zijun:
    Arg:
    1). rep: repository for the file
    2). fil1: filename
    3). tit1: title name
    4). slack_api: slack group channel api key
    5). channel: which channel wants to put 
'''
def slack_send_file(rep, fil1, tit1, slack_api, channel):
    client = sl.WebClient(token=slack_api)
    with open(rep, 'rb') as att:
        r = client.api_call("files.upload", files={'file': att,},
                            data={'channels': channel, 'filename': fil1, 'title': tit1, 'initial_comment': 'This is {}'.format(fil1),}
                            )
    assert r.status_code == 200


# #Zijun: This is function for auto uploading the file into dropbox
def dropbox_send_file(rep, file_name, dropbox_api_2):
    dropbox_api = dropbox.Dropbox(dropbox_api_2)
    with open(rep, "rb") as f:
        dropbox_api.files_upload(f.read(), file_name, mute=True)
    print ("Done uploading plot")
# Things we need from each experiment run
# name (dir), params that changed, values of changing parameters, metrics measured,

def get_metric_info(files):

    metric_info = {}

    for sub_paths in files.get_sub_paths_iterator():
        status = Status(sub_paths)

        if status.is_completed():
            params = status.m_params
            vals = status.m_vals
            log = status.m_log

            metric_info[status.m_name] = (params, vals, log)

    return metric_info


def create_bar(path, metric_name, params, settings, metric_values, slack_api, slack_api_2, channel):
    x_range = range(0, len(settings))

    fig, ax = plt.subplots()
    ax.bar(x_range, metric_values, width=0.3)
    ax.set_ylabel(metric_name)
    ax.set_title('{} by\n{}'.format(metric_name, params))
    ax.set_xticks(x_range)
    ax.set_xticklabels(settings)

    filename = path / viz_file_pattern_bar.format(metric_name)
    print(str(filename))
    fig.savefig(str(filename))
    slack_send_file(filename, viz_file_pattern_bar.format(metric_name), viz_file_pattern_bar.format(metric_name), slack_api, channel)
    dropbox_send_file(filename, "/Librec-auto/"+viz_file_pattern_bar.format(metric_name), slack_api_2)
    plt.close()
    return filename


def create_bars(path, metric_info, slack_api, slack_api_2, channel):
    metric_names = list(metric_info.values())[0][2].get_metrics()
    # Nasim: add list to it because in python 3 it returns a view, so it doesn't have indexing, you can't access it.
    bar_paths = []

    for metric in metric_names:

        param_string = ""
        settings = []
        metric_vals = []

        for params, vals, log in metric_info.values():
            param_string = ', '.join(params)
            settings.append('\n'.join(vals))
            metric_vals.append(float(log.get_metric_values(metric)[-1]))

        bar_paths.append(create_bar(path, metric, param_string, settings, metric_vals, slack_api, slack_api_2, channel))

    return bar_paths


def create_box(path, metric, params, settings, fold_values, slack_api, slack_api_2, channel):
    fig, ax = plt.subplots()
    ax.boxplot(fold_values)
    ax.set_ylabel(metric)
    ax.set_xticklabels(settings)
    ax.set_title('{} distribution by\n{}'.format(metric, params))

    filename = path / viz_file_pattern_box.format(metric)
    print (filename)
    fig.savefig(str(filename))
    slack_send_file(filename, viz_file_pattern_box.format(metric), viz_file_pattern_box.format(metric), slack_api, channel)
    dropbox_send_file(filename, "/Librec-auto/"+viz_file_pattern_box.format(metric), slack_api_2)
    plt.close()
    return filename


def create_boxes(path, metric_info, slack_api, slack_api_2, channel):
    metric_names = list(metric_info.values())[0][2].get_metrics()
    print(metric_names)

    box_paths = []
    for metric in metric_names:

        param_string = ""
        settings = []
        fold_vals = []

        for params, vals, log in metric_info.values():
            param_string = ', '.join(params)
            settings.append('\n'.join(vals))
            metric_vals = log.get_metric_values(metric)[:-1]
            fold_vals.append([float(val) for val in metric_vals])

        box_paths.append(create_box(path, metric, param_string, settings, fold_vals, slack_api, slack_api_2, channel))

    return box_paths

PAGE_TEMPLATE = '<html><h1>Study results</h1>{}</html>'
METRIC_TEMPLATE = '<h2>Metric: {}</h2>{}'
IMAGE_TEMPLATE = '<img src="{}" />'

def create_html(path, metric_info, bars, boxes):
    html = PAGE_TEMPLATE
    metric_chunks = []
    metric_names = list(metric_info.values())[0][2].get_metrics()

    if boxes is None:
        for name, bar in zip(metric_names, bars):
            images = IMAGE_TEMPLATE.format(bar.name)
            metric_chunks.append(METRIC_TEMPLATE.format(name, images))
    else:
        for name, bar, box in zip(metric_names, bars, boxes):
            images = IMAGE_TEMPLATE.format(bar.name) + IMAGE_TEMPLATE.format(box.name)
            metric_chunks.append(METRIC_TEMPLATE.format(name, images))

    output = html.format('\n'.join(metric_chunks))

    filename = path / viz_html_filename

    with open(filename, 'w') as out_file:
     out_file.write(output)

    return filename


def create_graphics(config, display, slack_api, slack_api_2, channel):
    files = config.get_files()
    metric_info = get_metric_info(config.get_files())

    bars = create_bars(files.get_post_path(), metric_info, slack_api, slack_api_2, channel)

    if 'data.splitter.cv.number' in config.get_prop_dict():         # Box plot only makes sense for cross-validation
        boxes = create_boxes(files.get_post_path(), metric_info, slack_api, slack_api_2, channel)
    else:
        boxes = None

    if display:
        html_file = create_html(files.get_post_path(), metric_info, bars, boxes)
        webbrowser.open('file://' + str(html_file.absolute()), new=1, autoraise=True)

def decrypted_function(repo_key1, repo_encrypted_file, repo_decrypted_file):
    file = open(repo_key1, "rb")
    key = file.read()
    file.close()

    with open(repo_encrypted_file, "rb") as api:
        data = api.read()
    fernet = Fernet(key)
    encrypted = fernet.decrypt(data)
    with open(repo_decrypted_file,"wb") as decry:
        decry.write(encrypted)

def decrypted_file_Dropbox(repo_key, repo_encrypted_Dropbox_file, repo_decrypted_Dropbox_file):
    file = open(repo_key, "rb")
    key = file.read()
    file.close()

    with open(repo_encrypted_Dropbox_file, "rb") as api:
        data = api.read()
    fernet = Fernet(key)
    encrypted = fernet.decrypt(data)
    with open(repo_decrypted_Dropbox_file,"wb") as decry:
        decry.write(encrypted)

def read_args():
    """
    Parse command line arguments.
    :return:
    """
    parser = argparse.ArgumentParser(description='Generic post-processing script')
    parser.add_argument('conf', help='Path to configuration file')
    parser.add_argument('target', help='Experiment target')
    parser.add_argument('--browser', help='Show graphics in browser', choices=['True', 'False'])
    parser.add_argument('--channel', help='Input slack channel')
    parser.add_argument('--decrypted_file', help="repository of decrypted slack api key file")
    parser.add_argument('--encrypted_file', help="repository of encrpyted slack api key file")
    parser.add_argument('--key', help="repository of key file")
    parser.add_argument('--decrypted_Dropbox_file', help="repository of decrypted Dropbox api key file")
    parser.add_argument('--encrypted_Dropbox_file', help="repository of encrypted Dropbox api key file")
    input_args = parser.parse_args()
    return vars(input_args)


if __name__ == '__main__':
    args = read_args()
    config = read_config_file(args['conf'], args['target'])

    print(f"librec-auto: Creating summary visualizations for {args['target']}")

    display = args['browser'] == 'True'
    channel = args['channel']
    decrypted_file = args['decrypted_file']
    encrypted_file = args['encrypted_file']
    key_file = args['key']

    decrypted_Dropbox_file = args['decrypted_Dropbox_file']
    encrypted_Dropbox_file = args["encrypted_Dropbox_file"]

    decrypted_function(str(key_file), str(encrypted_file), str(decrypted_file))
    decrypted_file_Dropbox(str(key_file), str(encrypted_Dropbox_file), str(decrypted_Dropbox_file))
    with open(decrypted_file, "r") as file:
        slack_api_1 = file.read()
    with open(decrypted_Dropbox_file, "r") as file:
        Dropbox_api = file.read()
    create_graphics(config, display, slack_api_1, Dropbox_api, channel)
