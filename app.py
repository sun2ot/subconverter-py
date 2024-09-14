from flask import Flask, jsonify, request, make_response
import requests
import yaml
import re
from collections import deque
import io

app = Flask(__name__)

def insert_flag(sub_data, emoji_path):
    # 匹配所有旗帜符号的正则表达式（Unicode 区域旗帜字符）
    flag_regex = r'[\U0001F1E6-\U0001F1FF]{2}'
    emoji_rule_list = []
    with open(emoji_path, 'r', encoding='utf-8') as emoji_rules:
        for line in emoji_rules:
            line = line.strip()  # 去除两边空格
            if not line or line.startswith('#'):
                continue  # 跳过空行和注释
            emoji_rule_list.append(line)
    # 遍历节点名称
    for idx, node in enumerate(sub_data['proxies']):
        matched = False  # 标记是否有匹配成功
        for rule in emoji_rule_list:
            # 解析每一条规则
            regex_pattern, flag = rule.split(',')
            
            # 检查节点名称是否匹配这条规则
            if re.search(regex_pattern, node['name']):
                # 匹配成功，去掉节点名称中的对应旗帜符号
                delete_flag = re.sub(flag_regex, '', node['name']).strip()
                final_name = f'{flag} {delete_flag}'
                sub_data['proxies'][idx]['name'] = final_name
                matched = True
                break  # 已匹配，跳出规则循环
        if not matched:
            print(f"{node['name']}未匹配任何规则")
    
    return sub_data


def parse_config(model_path, config_path, sub_data):
    """
    读取配置文件
    Args:
        model_path (str): 模板文件路径
        config_path (str): 配置文件路径
        sub_data (yaml.safe_load): 订阅数据
    """
    rulesets = []
    groups = []

    with open(config_path, 'r', encoding='utf-8') as config:
        for line in config:
            line = line.strip()
            if not line or line.startswith(';'): continue  # 注释/空行
            item, content = line.split('=')
            if item == 'ruleset':
                # [group_name, type, link]
                #todo typehint
                rulesets.append(content.split(','))
            if item == 'proxy_group':
                # 1. [group_name, group_type, reg, [...]]
                # 2. [group_name, group_type, reg]
                # 3. [group_name, group_type, [...]]
                groups.append(content.split('`'))
            if item == 'emoji':
                sub_data = insert_flag(sub_data, content)

    with open(model_path, 'r', encoding='utf-8') as base:
        base_data = yaml.safe_load(base)

        # 添加节点
        base_data['proxies'] = sub_data['proxies']
        node_names = [node['name'] for node in base_data['proxies']]

        # 添加策略组
        for group in groups:
            #todo typehint
            proxy_group = {
                'name': group[0],
                'type': group[1],
                'proxies': deque([])
            }
            if group[2].startswith('('):  # 正则匹配
                group_reg = group[2]
                for name in node_names:
                    if re.match(group_reg, name):
                        proxy_group['proxies'].append(name)
                for remain in group[3:]:  # 嵌套策略组
                    proxy_group['proxies'].appendleft(remain)
            else:  # 只有策略组
                proxy_group['proxies'].extend(group[2:])
            proxy_group['proxies'] = list(proxy_group['proxies'])

            # 添加到模板
            base_data['proxy-groups'].append(proxy_group)

        # 添加 rule & rule-provider
        rules = []
        providers = {}  #* rul3-providers 是个dict，不是list
        for rule_set in rulesets:
            set_name = rule_set[2].split('/')[-1].split('.')[0]  # 规则集名 <- url的文件名
            set_type = rule_set[1]  # 规则集类型
            proxy_group = rule_set[0]  # 策略组名

            rules.append(f'RULE-SET,{set_name},{proxy_group}')  # 添加规则

            provider_config = {
                'type': 'http',  #todo 搞忘了，规则集好像也有本地的，不过我本人不用，就先算了
                'behavior': set_type,  # classic, domain, ipcidr
                'url': rule_set[2],
                'path': f'./providers/rule-provider_{set_name}.yaml',
                'interval': 86400,
            }
            providers[set_name] = provider_config

        # 添加到模板
        base_data['rules'] = rules
        base_data['rule-providers'] = providers
    return base_data

@app.route('/generate', methods=['GET'])
def generate(model_path='templates/base.yaml', config_path='test.ini'):
    link = request.args.get('link')  # 从URL参数获取链接
    header = {'user-agent': 'clash-verge/v1.7.7'}
    origin_response = requests.get(link, headers=header)  # 获取订阅文件
    sub_data = yaml.safe_load(origin_response.text)
    subscription = parse_config(model_path, config_path, sub_data)

    yaml_result = yaml.dump(subscription, allow_unicode=True, encoding='utf-8')

    # 使用 io.BytesIO 创建一个文件流
    file_stream = io.BytesIO()
    file_stream.write(yaml_result)  # 将内容写入文件流，编码为utf-8
    file_stream.seek(0)  # 重置指针到文件开头


    # 创建响应并指定文件下载的文件名和MIME类型
    response = make_response(file_stream.read())
    response.headers['Content-Disposition'] = 'attachment; filename=generated.yaml'
    # 这里面是流量使用信息
    response.headers['subscription-userinfo'] = origin_response.headers['subscription-userinfo']
    response.mimetype = 'text/yaml; charset=utf-8'
    return response

@app.route('/')
def main():
    return jsonify({"status": "success", "message": "Hello"}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
