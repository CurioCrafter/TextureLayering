"""Build a separate native workspace after Blender completes its screen switch."""
import bpy
from bpy.types import Operator

_PENDING=[]


def focus_desk_panels():
    for window in bpy.context.window_manager.windows:
        if window.workspace.name != 'Shipwreck Desk':
            continue
        for area in window.screen.areas:
            if area.type not in {'VIEW_3D','IMAGE_EDITOR'}:
                continue
            for region in area.regions:
                if region.type != 'UI' or not region.width:
                    continue
                try:
                    with bpy.context.temp_override(window=window,area=area,region=region):
                        region.active_panel_category='Shipwreck Desk'
                except (AttributeError,TypeError,ValueError):
                    pass  # Some Blender builds require one manual sidebar-tab click.
            area.tag_redraw()
    return None


def _build_pending():
    # One topology change per UI event-loop turn. Reusing area pointers after a
    # close/split can crash Blender before Python has a chance to raise an error.
    for item in list(_PENDING):
        window,workspace,source_screen,attempt,stage=item
        try:
            if window.workspace!=workspace or (source_screen and window.screen==source_screen):
                item[3]+=1
                if attempt<20:
                    continue
                raise RuntimeError('Workspace switch was interrupted; open the desk again')
            areas=list(window.screen.areas)
            if stage=='CLOSE':
                main=max(areas,key=lambda a:a.width*a.height)
                others=[a for a in areas if a!=main]
                if others:
                    with bpy.context.temp_override(window=window,area=others[0]):
                        result=bpy.ops.screen.area_close()
                    if 'FINISHED' not in result:
                        item[4]='SPLIT'
                    continue
                item[4]='SPLIT'
            if item[4]=='SPLIT':
                main=max(window.screen.areas,key=lambda a:a.width*a.height)
                with bpy.context.temp_override(window=window,area=main):
                    main.type='VIEW_3D'
                    result=bpy.ops.screen.area_split(direction='VERTICAL',factor=.53)
                if 'FINISHED' not in result:
                    raise RuntimeError('Blender did not create the image canvas')
                item[4]='CONFIGURE'
                continue
            main_areas=sorted(window.screen.areas,key=lambda a:a.width*a.height,reverse=True)[:2]
            if len(main_areas)!=2:
                raise RuntimeError('Two editing areas are required')
            left,right=sorted(main_areas,key=lambda a:a.x)
            with bpy.context.temp_override(window=window,area=left):
                left.type='VIEW_3D'
                left.spaces.active.shading.type='MATERIAL'
                left.spaces.active.overlay.show_overlays=False
                left.spaces.active.show_region_ui=True
            with bpy.context.temp_override(window=window,area=right):
                right.type='IMAGE_EDITOR'
                right.spaces.active.mode='PAINT'
                right.spaces.active.show_region_ui=True
                right.spaces.active.show_region_toolbar=True
            from .operators.common import require_active_layer
            with bpy.context.temp_override(window=window):
                _,layer=require_active_layer(bpy.context)
            if layer and layer.mask_image:
                right.spaces.active.image=layer.mask_image
            workspace['sls_desk_ready']=True
            window.scene.sls_desk.status='Desk ready. Select the Shipwreck Desk sidebar tab if it is not visible.'
            bpy.app.timers.register(focus_desk_panels,first_interval=.6)
        except (RuntimeError,ValueError,ReferenceError) as exc:
            if window in tuple(bpy.context.window_manager.windows):
                window.scene.sls_desk.status=f'Workspace setup stopped: {exc}. Original layout retained.'
        _PENDING.remove(item)
    return .15 if _PENDING else None


class SLS_OT_desk_workspace(Operator):
    bl_idname='sls.desk_workspace'
    bl_label='Open Shipwreck Desk'
    bl_description='Open a separate workspace with a 3D material view, image canvas, and editing panels'

    @classmethod
    def poll(cls,context):
        return context.window is not None and not bpy.app.background

    def execute(self,context):
        window=context.window
        if _PENDING:
            return {'FINISHED'}
        existing=bpy.data.workspaces.get('Shipwreck Desk')
        if existing and existing.get('sls_desk_ready'):
            window.workspace=existing
            bpy.app.timers.register(focus_desk_panels,first_interval=.6)
            return {'FINISHED'}
        source_screen=window.screen
        try:
            if existing:
                created=existing
            else:
                before=set(bpy.data.workspaces)
                bpy.ops.workspace.duplicate()
                created=next((w for w in bpy.data.workspaces if w not in before),None)
                if created is None:
                    raise RuntimeError('Blender did not duplicate the workspace')
                created.name='Shipwreck Desk'
            window.workspace=created
            # RNA switching is deferred to the UI event loop. Editing window.screen
            # here would modify the ORIGINAL workspace, not the new one.
            _PENDING.append([window,created,source_screen if window.workspace!=created else None,0,'CLOSE'])
            bpy.app.timers.register(_build_pending,first_interval=.1)
            context.scene.sls_desk.status='Opening the separate texture workspace…'
            return {'FINISHED'}
        except (RuntimeError,ValueError) as exc:
            self.report({'ERROR'},f'Workspace setup: {exc}')
            return {'CANCELLED'}


def register():
    bpy.utils.register_class(SLS_OT_desk_workspace)


def unregister():
    _PENDING.clear()
    for timer in (_build_pending,focus_desk_panels):
        if bpy.app.timers.is_registered(timer):
            bpy.app.timers.unregister(timer)
    bpy.utils.unregister_class(SLS_OT_desk_workspace)
