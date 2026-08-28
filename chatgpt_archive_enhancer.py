#!/usr/bin/env python3
"""Enhance ChatGPT data exports and create true-delta archives.

Runs entirely locally; no network access, OpenAI API key, cookies, or credentials.
"""
from __future__ import annotations
import argparse, copy, json, re, sys, zipfile
from pathlib import Path

JSON_KW = dict(ensure_ascii=False, separators=(",", ":"))

EXTRA_CSS = r'''
      /* ChatGPT Archive Enhancer */
      body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#fff; color:#111; }
      #archive-layout { display:flex; min-height:100vh; }
      #sidebar { width:330px; min-width:330px; height:100vh; position:sticky; top:0; overflow-y:auto; box-sizing:border-box; padding:18px 14px; border-right:1px solid #d9d9d9; background:#fafafa; }
      #sidebar h2 { font-size:18px; margin:0 0 6px; }
      #sidebar .archive-note { font-size:12px; color:#666; margin-bottom:12px; }
      #conversation-search { width:100%; box-sizing:border-box; padding:9px 10px; margin:0 0 12px; border:1px solid #bbb; border-radius:6px; font-size:14px; background:white; }
      #conversation-index { display:flex; flex-direction:column; gap:4px; }
      .index-item { display:block; padding:8px 9px; border-radius:6px; text-decoration:none; color:#111; }
      .index-item:hover { background:#ececec; }
      .index-title { display:block; font-size:13px; font-weight:600; line-height:1.25; }
      .index-date { display:block; margin-top:2px; font-size:11px; color:#666; }
      #root { flex:1; min-width:0; padding:20px; display:flex; flex-direction:column; gap:20px; }
      .conversation { scroll-margin-top:12px; border:1px solid #bbb; border-radius:8px; padding:20px; background:#f7f7f7; }
      .conversation-meta { margin:5px 0 16px; font-size:12px; color:#555; }
      .conversation-meta span + span::before { content:"  •  "; color:#999; }
      .thread-actions { display:flex; align-items:center; gap:10px; margin:0 0 18px; }
      .pdf-button { appearance:none; border:1px solid #777; border-radius:7px; background:#fff; color:#111; padding:8px 12px; font:inherit; font-size:13px; font-weight:600; cursor:pointer; }
      .pdf-button:hover { background:#ececec; }
      .pdf-hint { font-size:11px; color:#666; }
      @media print {
        @page { margin:.55in; }
        body { background:#fff !important; color:#000 !important; }
        #sidebar,.thread-actions { display:none !important; }
        #archive-layout { display:block !important; }
        #root { padding:0 !important; margin:0 !important; }
        body.print-one .conversation { display:none !important; }
        body.print-one .conversation.print-target { display:block !important; border:0 !important; border-radius:0 !important; padding:0 !important; margin:0 !important; background:#fff !important; }
        body.print-one .conversation.print-target h4 { font-size:20pt; margin:0 0 6pt; }
        body.print-one .conversation-meta { margin-bottom:18pt; color:#444 !important; }
        body.print-one .message { white-space:pre-wrap !important; overflow-wrap:anywhere; max-width:100%; box-sizing:border-box; }
        body.print-one img,body.print-one video,body.print-one svg { max-width:100% !important; height:auto !important; }
        body.print-one a { color:#000 !important; text-decoration:underline; }
      }
      @media (max-width:850px) { #archive-layout{display:block} #sidebar{position:relative;width:100%;min-width:0;height:auto;max-height:40vh;border-right:0;border-bottom:1px solid #d9d9d9} }
'''

BODY = '''<body>\n    <div id="archive-layout">\n      <aside id="sidebar">\n        <h2>ChatGPT Archive</h2>\n        <div class="archive-note">Newest first · dates shown in Pacific Time</div>\n        <input id="conversation-search" type="search" placeholder="Search conversations or dates…" aria-label="Search conversations">\n        <nav id="conversation-index"></nav>\n      </aside>\n      <main id="root"></main>\n    </div>\n  </body>'''

ONLOAD = r'''window.onload = function() {
          function pacificDate(ts, detailed) {
              if (!ts) return "Unknown";
              var opts = detailed
                ? {timeZone:"America/Los_Angeles",year:"numeric",month:"long",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}
                : {timeZone:"America/Los_Angeles",year:"numeric",month:"short",day:"numeric"};
              return new Intl.DateTimeFormat("en-US", opts).format(new Date(ts * 1000));
          }
          function anchorId(c, i) { return "conversation-" + (c.id || c.conversation_id || i).replace(/[^A-Za-z0-9_-]/g,"-"); }
          function cleanTitle(s) { return (s || "Untitled conversation").replace(/[\\/:*?"<>|]/g,"-").slice(0,120); }
          var printState = {target:null, oldTitle:null};
          function clearPrintMode(){ document.body.classList.remove("print-one"); if(printState.target) printState.target.classList.remove("print-target"); if(printState.oldTitle!==null) document.title=printState.oldTitle; printState={target:null,oldTitle:null}; }
          window.addEventListener("afterprint", clearPrintMode);
          function exportPdf(div,c){ printState.target=div; printState.oldTitle=document.title; div.classList.add("print-target"); document.body.classList.add("print-one"); document.title=cleanTitle((c.title||"Untitled conversation")+" - "+pacificDate(c.create_time,false)); window.print(); }

          var root=document.getElementById("root"), indexRoot=document.getElementById("conversation-index"), search=document.getElementById("conversation-search");
          var conversations=jsonData.slice().sort(function(a,b){return (b.create_time||0)-(a.create_time||0)}), indexItems=[];
          for(var i=0;i<conversations.length;i++){
              var conversation=conversations[i], messages=getConversationMessages(conversation), aid=anchorId(conversation,i);
              var div=document.createElement("div"); div.className="conversation"; div.id=aid;
              var title=document.createElement("h4"); title.textContent=conversation.title||"Untitled conversation"; div.appendChild(title);
              var meta=document.createElement("div"); meta.className="conversation-meta";
              var started=document.createElement("span"); started.textContent="Started: "+pacificDate(conversation.create_time,true);
              var updated=document.createElement("span"); updated.textContent="Last updated: "+pacificDate(conversation.update_time,true);
              meta.appendChild(started); meta.appendChild(updated); div.appendChild(meta);
              var actions=document.createElement("div"); actions.className="thread-actions";
              var btn=document.createElement("button"); btn.type="button"; btn.className="pdf-button"; btn.textContent="Export this thread to PDF";
              (function(d,c){btn.addEventListener("click",function(){exportPdf(d,c)})})(div,conversation);
              var hint=document.createElement("span"); hint.className="pdf-hint"; hint.textContent="Opens the print dialog with only this thread.";
              actions.appendChild(btn); actions.appendChild(hint); div.appendChild(actions);
              for(var j=0;j<messages.length;j++){
                  var message=document.createElement("pre"); message.className="message";
                  var author=document.createElement("div"); author.className="author"; author.textContent=messages[j].author; message.appendChild(author);
                  if(messages[j].parts){ var mid=messages[j].id;
                    for(var k=0;k<messages[j].parts.length;k++){ var part=messages[j].parts[k]; if(part.text) appendTextDiv(message,part.text); else if(assetsJson&&part.transcript) appendTextDiv(message,"[Transcript]: "+part.transcript); }
                    if(assetsJson&&Object.prototype.hasOwnProperty.call(assetsJson,mid)){ var names=assetsJson[mid]; for(var l=0;l<names.length;l++){ var fd=document.createElement("div"); fd.append("[File]: "); var a=document.createElement("a"); a.href=names[l]; a.textContent=names[l]; fd.appendChild(a); message.appendChild(fd); } }
                  }
                  div.appendChild(message);
              }
              root.appendChild(div);
              var link=document.createElement("a"); link.className="index-item"; link.href="#"+aid;
              var it=document.createElement("span"); it.className="index-title"; it.textContent=conversation.title||"Untitled conversation";
              var idate=document.createElement("span"); idate.className="index-date"; idate.textContent=pacificDate(conversation.create_time,false);
              link.appendChild(it); link.appendChild(idate); indexRoot.appendChild(link);
              indexItems.push({el:link,search:((conversation.title||"")+" "+pacificDate(conversation.create_time,true)).toLowerCase()});
          }
          search.addEventListener("input",function(){var q=search.value.trim().toLowerCase(); indexItems.forEach(function(x){x.el.style.display=(!q||x.search.indexOf(q)!==-1)?"block":"none"})});
      }'''


def load_json(z, name, default):
    try: return json.loads(z.read(name))
    except KeyError: return copy.deepcopy(default)


def conv_id(c): return c.get("conversation_id") or (c.get("id") if isinstance(c.get("id"), str) else None)


def fingerprint(c):
    """Fingerprint the visible current conversation branch, not volatile export metadata."""
    trail=[]
    cur=c.get("current_node")
    mapping=c.get("mapping") or {}
    seen=set()
    while cur and cur not in seen:
        seen.add(cur)
        node=mapping.get(cur) or {}
        msg=node.get("message")
        if msg:
            content=msg.get("content") or {}
            trail.append({
                "id":msg.get("id"),
                "author":(msg.get("author") or {}).get("role"),
                "content_type":content.get("content_type"),
                "parts":content.get("parts"),
            })
        cur=node.get("parent")
    return json.dumps({"title":c.get("title"),"messages":trail}, sort_keys=True, ensure_ascii=False, separators=(",",":"))

def true_delta(old_convs, new_convs):
    old={conv_id(c):c for c in old_convs if conv_id(c)}
    out=[]
    for c in new_convs:
        cid=conv_id(c)
        if cid not in old or fingerprint(c)!=fingerprint(old[cid]): out.append(c)
    return out


def _embedded_json_span(html, varname):
    m=re.search(r"var\s+"+re.escape(varname)+r"\s*=\s*", html)
    if not m: raise ValueError(f"Could not locate {varname} in chat.html")
    decoder=json.JSONDecoder()
    obj, consumed=decoder.raw_decode(html[m.end():])
    return obj, m.end(), m.end()+consumed

def parse_embedded_var(html, varname):
    obj, _, _ = _embedded_json_span(html,varname)
    return obj

def replace_embedded_var(html,varname,obj):
    _, start, end = _embedded_json_span(html,varname)
    return html[:start]+json.dumps(obj,**JSON_KW)+html[end:]

def enhance_html(html, conversations, assets):
    html=replace_embedded_var(html,"jsonData",conversations)
    html=replace_embedded_var(html,"assetsJson",assets)
    html=html.replace("    </style>", EXTRA_CSS+"\n    </style>",1)
    start=html.find("window.onload = function()")
    if start<0: raise ValueError("Could not locate window.onload in chat.html")
    end=html.find("\n      }\n    </script>",start)
    if end<0: raise ValueError("Could not locate end of window.onload in chat.html")
    html=html[:start]+ONLOAD+html[end+9:]
    html=re.sub(r"<body>\s*<div id=\"root\"></div>\s*</body>",BODY,html,count=1)
    return html


def message_ids(convs):
    ids=set()
    for c in convs:
        for node in (c.get("mapping") or {}).values():
            m=node.get("message") or {}
            if m.get("id"): ids.add(m["id"])
    return ids


def rebuild_manifest(files):
    entries=[{"path":p,"size_bytes":len(b)} for p,b in sorted(files.items()) if p!="export_manifest.json"]
    logical={e["path"]:{"files":[e["path"]],"sharded":False} for e in entries}
    manifest={"export_files":entries,"logical_files":logical,"manifest_file":"export_manifest.json","version":1}
    return json.dumps(manifest,ensure_ascii=False,indent=2).encode()


def process(new_zip, output, old_zip=None):
    with zipfile.ZipFile(new_zip) as nz:
        names=set(nz.namelist()); new_convs=load_json(nz,"conversations.json",[])
        selected=new_convs
        summary={"mode":"enhance-full","new_export":Path(new_zip).name,"conversation_count":len(selected)}
        if old_zip:
            with zipfile.ZipFile(old_zip) as oz: old_convs=load_json(oz,"conversations.json",[])
            selected=true_delta(old_convs,new_convs)
            old_ids={conv_id(c) for c in old_convs}; new_count=sum(conv_id(c) not in old_ids for c in selected)
            summary={"mode":"true-delta","old_export":Path(old_zip).name,"new_export":Path(new_zip).name,"conversation_count":len(selected),"new_conversations":new_count,"modified_conversations":len(selected)-new_count}
        html=nz.read("chat.html").decode("utf-8")
        embedded_assets=parse_embedded_var(html,"assetsJson")
        mids=message_ids(selected)
        assets={mid:names_ for mid,names_ in embedded_assets.items() if mid in mids}
        asset_files={f for arr in assets.values() for f in arr}
        files={}
        # Keep account-level metadata for full enhancement; delta retains safe small metadata too.
        always={"user.json","user_settings.json","ads.json","shared_conversations.json"}
        for n in always:
            if n in names: files[n]=nz.read(n)
        files["conversations.json"]=json.dumps(selected,ensure_ascii=False,indent=2).encode()
        files["chat.html"]=enhance_html(html,selected,assets).encode()
        cam=load_json(nz,"conversation_asset_file_names.json",{})
        cam={k:v for k,v in cam.items() if k in asset_files}
        files["conversation_asset_file_names.json"]=json.dumps(cam,ensure_ascii=False,indent=2).encode()
        for f in asset_files:
            if f in names: files[f]=nz.read(f)
        libs=load_json(nz,"library_files.json",[])
        keep_file_ids={Path(f).stem for f in asset_files}
        libs=[x for x in libs if x.get("file_id") in keep_file_ids or x.get("origination_thread_id") in {conv_id(c) for c in selected}]
        files["library_files.json"]=json.dumps(libs,ensure_ascii=False,indent=2).encode()
        fb=load_json(nz,"message_feedback.json",[]); cids={conv_id(c) for c in selected}
        files["message_feedback.json"]=json.dumps([x for x in fb if x.get("conversation_id") in cids],ensure_ascii=False,indent=2).encode()
        summary["asset_files"]=len(asset_files)
        files["delta_summary.json"]=json.dumps(summary,ensure_ascii=False,indent=2).encode()
        files["ENHANCEMENTS.txt"]=("ChatGPT Archive Enhancer\n\nSearchable newest-first sidebar; Pacific-Time Started/Last updated metadata; per-thread PDF/print isolation.\n").encode()
        files["export_manifest.json"]=rebuild_manifest(files)
        with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as out:
            for n,b in files.items(): out.writestr(n,b)
    with zipfile.ZipFile(output) as test:
        bad=test.testzip()
        if bad: raise RuntimeError("ZIP integrity failure: "+bad)
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description="Enhance ChatGPT exports or create a true-delta archive.")
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--enhance", metavar="EXPORT.zip", help="Enhance a complete export")
    g.add_argument("--new", metavar="NEW.zip", help="Newer export for true-delta mode")
    p.add_argument("--old", metavar="OLD.zip", help="Older export for true-delta mode")
    p.add_argument("--output","-o",required=True,help="Output ZIP")
    a=p.parse_args(argv)
    if a.new and not a.old: p.error("--new requires --old")
    try:
        s=process(a.enhance or a.new,a.output,a.old if a.new else None)
        print(json.dumps(s,indent=2))
    except Exception as e:
        print("error:",e,file=sys.stderr); return 1
    return 0

if __name__=="__main__": raise SystemExit(main())
