import importlib.util, pathlib
P=pathlib.Path(__file__).parents[1]/"chatgpt_archive_enhancer.py"
spec=importlib.util.spec_from_file_location("cae",P); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def c(cid,title="x",text="hello",update=1):
    return {"id":cid,"title":title,"create_time":1,"update_time":update,"current_node":"n","mapping":{"n":{"id":"n","parent":None,"message":{"id":"m"+cid,"author":{"role":"user"},"content":{"content_type":"text","parts":[text]},"metadata":{}}}}}

def test_true_delta_new_and_modified():
    old=[c("A"),c("B")]
    new=[c("A",update=99),c("B",text="changed",update=2),c("C")]
    got=m.true_delta(old,new)
    assert [x["id"] for x in got]==["B","C"]

def test_update_time_only_is_not_a_change():
    assert m.true_delta([c("A",update=1)],[c("A",update=999)])==[]
