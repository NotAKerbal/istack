"""Bounded AT-SPI snapshots with ephemeral references, never screen-coordinate guesses."""
import time
import uuid
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi


class Accessibility:
    def __init__(self):
        self.refs = {}
        Atspi.set_timeout(500, 1000)

    def snapshot(self, app=None, max_nodes=250, max_depth=8):
        self.refs.clear()
        nodes = []
        truncated = False
        deadline = time.monotonic() + 5
        prefix = uuid.uuid4().hex[:10]
        def walk(obj, depth, parent=None):
            nonlocal truncated
            if len(nodes) >= max_nodes or time.monotonic() > deadline:
                truncated = True
                return
            try:
                role = obj.get_role_name()
                name = (obj.get_name() or '')[:500]
                ref = f'{prefix}:{len(nodes)}'
                states = obj.get_state_set()
                row = {'ref': ref, 'parent': parent, 'role': role, 'name': name,
                       'focused': states.contains(Atspi.StateType.FOCUSED),
                       'showing': states.contains(Atspi.StateType.SHOWING)}
                action = obj.get_action_iface()
                if action:
                    row['actions'] = [action.get_action_name(i) for i in range(min(action.get_n_actions(), 20))]
                # Do not extract text/value interfaces: these may contain passwords or huge documents.
                self.refs[ref] = (obj, time.monotonic())
                nodes.append(row)
                count = obj.get_child_count()
                if depth < max_depth:
                    for i in range(min(count, max_nodes)):
                        if len(nodes) >= max_nodes or time.monotonic() > deadline:
                            truncated = True
                            break
                        child = obj.get_child_at_index(i)
                        if child:
                            walk(child, depth + 1, ref)
                    if count > max_nodes:
                        truncated = True
                elif count:
                    truncated = True
            except Exception:
                pass  # One inaccessible process must not hide other applications.
        desktop = Atspi.get_desktop(0)
        for i in range(desktop.get_child_count()):
            child = desktop.get_child_at_index(i)
            if child and (not app or app.casefold() in (child.get_name() or '').casefold()):
                walk(child, 0)
        return {'nodes': nodes, 'truncated': truncated,
                'note': 'Application support varies. References expire after 60 seconds or the next snapshot.'}

    def action(self, ref, action, text=None):
        entry = self.refs.get(ref)
        if not entry or time.monotonic() - entry[1] > 60:
            raise ValueError('Expired accessibility reference. Take a new accessibility snapshot.')
        obj = entry[0]
        if obj.get_state_set().contains(Atspi.StateType.DEFUNCT):
            raise ValueError('Element no longer exists')
        if action == 'focus':
            component = obj.get_component_iface()
            success = bool(component and component.grab_focus())
        elif action == 'set_text':
            if obj.get_role() == Atspi.Role.PASSWORD_TEXT:
                raise ValueError('Use the application UI to enter password fields')
            editable = obj.get_editable_text_iface()
            success = bool(editable and editable.set_text_contents(text or ''))
        else:
            iface = obj.get_action_iface()
            if not iface:
                raise ValueError('Element has no accessible actions')
            names = [iface.get_action_name(i) for i in range(iface.get_n_actions())]
            if action not in names:
                raise ValueError('Choose an exact action name from this element: ' + ', '.join(names))
            success = bool(iface.do_action(names.index(action)))
        if not success:
            raise RuntimeError('Application rejected the accessibility action')
        return {'performed': action, 'ref': ref}
