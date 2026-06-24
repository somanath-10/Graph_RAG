from collections import defaultdict


def build_sprout_tree(source_units: list[dict], document_id: str) -> list[dict]:
    nodes: list[dict] = []
    root_id = f'{document_id}_root'
    nodes.append({
        'node_id': root_id,
        'document_id': document_id,
        'level': 'document',
        'source_unit_ids': [],
        'text': '',
        'parent_id': None,
        'child_ids': [],
        'page_start': None,
        'page_end': None,
        'section': 'Document',
    })

    section_nodes: dict[str, dict] = {}
    unit_by_id = {unit['source_id']: unit for unit in source_units}
    for unit in source_units:
        if unit.get('unit_type') != 'section':
            continue
        section_name = unit.get('section') or 'Section'
        section_id = f"{document_id}_sprout_section_{len(section_nodes) + 1}"
        node = make_node(section_id, document_id, 'section', [unit['source_id']], unit, root_id)
        node['section'] = section_name
        section_nodes[unit['source_id']] = node
        nodes.append(node)
        nodes[0]['child_ids'].append(section_id)

    paragraph_nodes: dict[str, dict] = {}
    for unit in source_units:
        if unit.get('unit_type') not in {'paragraph', 'claim', 'example'}:
            continue
        parent_section = section_nodes.get(unit.get('parent_id'))
        parent_id = parent_section['node_id'] if parent_section else root_id
        node_id = f"{unit['source_id']}_sprout"
        node = make_node(node_id, document_id, unit.get('unit_type') or 'paragraph', [unit['source_id']], unit, parent_id)
        paragraph_nodes[unit['source_id']] = node
        nodes.append(node)
        _append_child(nodes, parent_id, node_id)

    for unit in source_units:
        if unit.get('unit_type') != 'sentence':
            continue
        parent_paragraph = paragraph_nodes.get(unit.get('parent_id'))
        parent_id = parent_paragraph['node_id'] if parent_paragraph else root_id
        node_id = f"{unit['source_id']}_sprout"
        node = make_node(node_id, document_id, 'sentence', [unit['source_id']], unit, parent_id)
        nodes.append(node)
        _append_child(nodes, parent_id, node_id)

    rollup_text(nodes, unit_by_id)
    return nodes


def make_node(
    node_id: str,
    document_id: str,
    level: str,
    source_unit_ids: list[str],
    unit: dict,
    parent_id: str | None,
) -> dict:
    return {
        'node_id': node_id,
        'document_id': document_id,
        'level': level,
        'source_unit_ids': source_unit_ids,
        'text': unit.get('text') or '',
        'parent_id': parent_id,
        'child_ids': [],
        'page_start': unit.get('page_start'),
        'page_end': unit.get('page_end'),
        'section': unit.get('section'),
    }


def rollup_text(nodes: list[dict], unit_by_id: dict[str, dict]):
    by_id = {node['node_id']: node for node in nodes}
    for node in sorted(nodes, key=lambda n: len(n.get('child_ids') or []), reverse=True):
        if node.get('text'):
            continue
        texts = []
        for child_id in node.get('child_ids') or []:
            child = by_id.get(child_id)
            if child and child.get('text'):
                texts.append(child['text'])
            elif child:
                for source_id in child.get('source_unit_ids') or []:
                    source = unit_by_id.get(source_id)
                    if source and source.get('text'):
                        texts.append(source['text'])
        node['text'] = '\n\n'.join(texts)[:4000]


def _append_child(nodes: list[dict], parent_id: str, child_id: str):
    for node in nodes:
        if node['node_id'] == parent_id:
            node['child_ids'].append(child_id)
            return
