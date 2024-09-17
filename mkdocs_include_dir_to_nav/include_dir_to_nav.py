import logging
import json
import yaml
import re

from mkdocs.structure.files import File
from mkdocs.plugins import BasePlugin
from mkdocs.config import config_options
import mkdocs.structure.nav as nav

log = logging.getLogger('mkdocs')

class IncludeDirToNav(BasePlugin):

    config_scheme = (
        ("flat", config_options.Type(bool, default=False)),
        ("file_pattern", config_options.Type(str, default='.*\.md$')),
        ("file_name_as_title", config_options.Type(bool, default=True)),
        ("recurse", config_options.Type(bool, default=True)),
        ("reverse_sort_directory", config_options.Type(bool, default=False)),
    )

    def on_files(self, files, config):
        if config["nav"]:
            log.debug(f"IncludeDirToNav : ## Original NAV : \n{yaml.dump(config['nav'], indent=2)}##")

            docs_pages = set(f.src_uri for f in files.documentation_pages())

            parse(
                ori_nav=config["nav"],
                docs_pages=docs_pages,
                config=config,
                pattern=self.config['file_pattern'],
                flat=self.config['flat'],
                file_name_as_title=self.config['file_name_as_title'],
                reverse_sort=self.config['reverse_sort_directory'],
            )
            log.debug(f"IncludeDirToNav : ## Final NAV : \n{yaml.dump(config['nav'], indent=2)}##")

### Loop over ori_nav in order to find PagePath
#### When found, check if pagePath is folder
#### If Yes, get direct files and direct directory, and insert it to nav
#### If direct directory was finding, recall parse with current index, in order to subCheck needsted folder
#### Take care of direct notation ( - myFolder ) and page title notation ( - my folder : myFolder)
def parse(ori_nav,config, docs_pages, pattern: str = '.*\.md$', flat: bool = False, previous=None, file_name_as_title: bool=False, recurse: bool=True, reverse_sort: bool=False):
    log.debug("IncludeDirToNav : ##START Parse state###")
    log.debug(f"IncludeDirToNav : ori_nav = {ori_nav} | previous = {previous} | type of ori_nav {type(ori_nav)}")

    ## Loop over nav path
    if isinstance(ori_nav, dict) or isinstance(ori_nav, list):
        for index, item in enumerate(ori_nav):
            ## If dict, value like { - 'pageName' : 'pagePath' }
            if isinstance(item, dict):
                log.debug(f"  IncludeDirToNav : Item in loop is dict. Item = {item}")
                ## Item hav only 1 value by mkdocs design, how but loop over ...
                for k in item:
                    ## If item value is List, value like { - 'pageName' : ['pagePath01', 'pagePath02' ...] }
                    ### Need to nested loop
                    if isinstance(item[k], list):
                        log.debug(f"    IncludeDirToNav : Item is List, recall parse. Item = {item[k]}")
                        parse(
                            ori_nav=item[k],
                            docs_pages=docs_pages,
                            config=config,
                            pattern=pattern,
                            flat=flat,
                            previous=item,
                            file_name_as_title=file_name_as_title,
                            recurse=recurse,
                            reverse_sort=reverse_sort,
                        )

                    ## Else, item is simple dict, aka, value is string
                    else:
                        log.debug(f"    IncludeDirToNav : check current item : {item[k]}")
                        to_add, directory_was_inserted = _generate_nav(item[k], docs_pages, pattern, flat, file_name_as_title, recurse, reverse_sort)
                        if to_add:
                            item.update({k: to_add})
                            if directory_was_inserted:
                                parse(
                                    ori_nav=item[k],
                                    docs_pages=docs_pages,
                                    config=config,
                                    pattern=pattern,
                                    flat=flat,
                                    previous=item,
                                    file_name_as_title=file_name_as_title,
                                    recurse=recurse,
                                    reverse_sort=reverse_sort,
                                )
            ## Else if item is no named, value like { - 'pagePath' }
            elif isinstance(item, str):
                log.debug(f"  IncludeDirToNav : Item in loop is string. Item = {item}")
                to_add, directory_was_inserted = _generate_nav(item, docs_pages, pattern, flat, file_name_as_title, recurse, reverse_sort)
                if to_add:
                    # Replace current index by object in order to avoid infinite loop
                    ori_nav[index] = to_add.pop(-1)
                    ## Now, index position is an object, so insert new value
                    for insert_index, insert in enumerate(to_add):
                        ori_nav.insert(index + insert_index, insert)
                    if directory_was_inserted:
                        parse(
                            # ori_nav=ori_nav[index],
                            ori_nav=ori_nav,
                            docs_pages=docs_pages,
                            config=config,
                            pattern=pattern,
                            flat=flat,
                            previous=ori_nav[index],
                            file_name_as_title=file_name_as_title,
                            recurse=recurse,
                            reverse_sort=reverse_sort,
                        )
def _generate_nav(current_item: str, docs_pages, pattern: str, flat, file_name_as_title, recurse, reverse_sort):
    ## Init var
    directory_was_inserted = False
    inserted_dirs = set()
    to_add = []

    ## Check if value is directory
    if current_item not in docs_pages:
        top_level = len(current_item.strip('/').split('/')) + 1
        log.debug(f"IncludeDirToNav_generate_nav : Current item maybe is a dir ({current_item})")

        for doc_page_uri in sorted(filter(lambda f: f.startswith(current_item), docs_pages), reverse=reverse_sort):
            uri_parts = doc_page_uri.split('/')
            file_name = uri_parts[-1]
            file_level = len(uri_parts)
            if (file_level == top_level) or flat:
                if re.match(pattern, file_name):
                    if file_name_as_title:
                        to_add.append(doc_page_uri)
                    else:
                        to_add.append({ '/'.join(uri_parts[:-1]) : doc_page_uri })
            elif recurse and (file_level >= top_level + 1):
                directory_was_inserted = True
                dir = '/'.join(uri_parts[:top_level])
                if dir not in inserted_dirs:
                    inserted_dirs.add(dir)
                    to_add.append({ uri_parts[top_level - 1] : dir })

    return to_add, directory_was_inserted
