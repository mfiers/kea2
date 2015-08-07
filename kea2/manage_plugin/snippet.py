
import kea2.util
import kea2.log

lg = kea2.log.get_logger(__name__, 'debug')
  

def list_all_snippets(meta):
    findpat = meta['_args'].find_pattern
    for group, name in kea2.util.list_templates(meta):
        assert name.endswith('.k2')
        outname = "%s:%s" % (group, name[:-3])
        if findpat:
            if findpat in outname:
                print(outname)
        else:
            print(outname)

   
    
def show_raw_snippet(meta):
    template_name = meta['_args'].template
    lg.debug("show raw template for %s",  template_name)
    template = kea2.util.get_template(meta, template_name)
    print(template)
    
    

def init(meta):
    list_sp = kea2.util.register_command(meta, 'list', list_all_snippets)
    list_sp.add_argument('find_pattern', nargs='?')
    
    raw_sp = kea2.util.register_command(meta, 'raw', show_raw_snippet)
    raw_sp.add_argument('template')
    
