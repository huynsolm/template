"""Unambiguous JSON extraction without modifying copy."""
import json
import re


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError(f'duplicate JSON key: {key}')
        result[key]=value
    return result


def extract_json(answer):
    fenced=re.findall(r'```json\s*\n?(.*?)```',answer,re.S|re.I)
    if fenced:
        if len(fenced)!=1: raise ValueError('answer: multiple JSON code blocks; provide exactly one')
        outside=re.sub(r'```json\s*\n?.*?```','',answer,flags=re.S|re.I)
        if '{' in outside or '}' in outside:
            raise ValueError('answer: ambiguous JSON objects outside code block')
        value=json.loads(fenced[0],object_pairs_hook=unique_object)
        if not isinstance(value,dict): raise ValueError('answer: JSON object required')
        return value
    objects=[]
    start=None; depth=0; quoted=False; escaped=False
    for i,char in enumerate(answer):
        if start is None:
            if char=='{': start=i; depth=1; quoted=False; escaped=False
            continue
        if quoted:
            if escaped: escaped=False
            elif char=='\\': escaped=True
            elif char=='"': quoted=False
        elif char=='"': quoted=True
        elif char=='{': depth+=1
        elif char=='}':
            depth-=1
            if depth==0:
                objects.append(answer[start:i+1]); start=None
    if start is not None or len(objects)!=1:
        raise ValueError('answer: provide exactly one complete JSON object')
    value=json.loads(objects[0],object_pairs_hook=unique_object)
    if not isinstance(value,dict): raise ValueError('answer: JSON object required')
    return value
