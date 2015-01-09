from UM.Math.Matrix import Matrix
from UM.Math.Vector import Vector
from UM.Math.AxisAlignedBox import AxisAlignedBox
from UM.Signal import Signal, SignalEmitter
from UM.Job import Job

from copy import copy, deepcopy

import math

##  A scene node object.
#
#   These objects can hold a mesh and multiple children. Each node has a transformation matrix
#   that maps it it's parents space to the local space (it's inverse maps local space to parent).
#
#   \todo Add unit testing
class SceneNode(SignalEmitter):
    def __init__(self, parent = None):
        super().__init__() # Call super to make multiple inheritence work.

        self._children = []
        self._mesh_data = None
        self._transformation = Matrix()
        self._parent = parent
        self._locked = False
        self._selectionMask = 0
        self._aabb = None
        self._aabbJob = None
        self._visible = True

        if parent:
            parent.addChild(self)

    ##  \brief Get the parent of this node. If the node has no parent, it is the root node.
    #   \returns SceneNode if it has a parent and None if it's the root node.
    def getParent(self):
        return self._parent

    ##  \brief Set the parent of this object
    #   \param scene_node SceneNode that is the parent of this object.
    def setParent(self, scene_node):
        if self._parent:
            self._parent.removeChild(self)

        if scene_node:
            scene_node.addChild(self)

    ##  Emitted whenever the parent changes.
    parentChanged = Signal()

    ##  \brief Get the visibility of this node. The parents visibility overrides the visibility.
    #   TODO: Let renderer actually use the visibility to decide wether to render or not.
    def getVisibility(self):
        if self._parent != None:
            return parent.getVisibility()
        else:
            return self._visible
    
    def setVisibility(self):
        return self._visible

    ##  \brief Get the (original) mesh data from the scene node/object. 
    #   \returns MeshData
    def getMeshData(self):
        return self._mesh_data

    ##  \brief Get the transformed mesh data from the scene node/object, based on the transformation of scene nodes wrt root. 
    #   \returns MeshData    
    def getMeshDataTransformed(self):
        transformed_mesh = deepcopy(self._mesh_data)
        transformed_mesh.transform(self.getGlobalTransformation())
        return transformed_mesh

    ##  \brief Set the mesh of this node/object
    #   \param mesh_data MeshData object
    def setMeshData(self, mesh_data):
        self._mesh_data = mesh_data
        self._resetAABB()
        self.meshDataChanged.emit(self)

    ##  Emitted whenever the attached mesh data object changes.
    meshDataChanged = Signal()

    ##  \brief Add a child to this node and set it's parent as this node.
    #   \params scene_node SceneNode to add.
    def addChild(self, scene_node):
        if scene_node not in self._children:
            scene_node.transformationChanged.connect(self.transformationChanged)
            scene_node.childrenChanged.connect(self.childrenChanged)
            self._children.append(scene_node)
            self._aabb = None
            self.childrenChanged.emit(self)

            if not scene_node._parent is self:
                scene_node._parent = self
                scene_node.parentChanged.emit(self)
    
    ##  \brief remove a single child
    #   \param child Scene node that needs to be removed. 
    def removeChild(self, child):
        if child not in self._children:
            return

        child.transformationChanged.disconnect(self.transformationChanged)
        child.childrenChanged.disconnect(self.childrenChanged)
        self._children.remove(child)
        child._parent = None
        child.parentChanged.emit(self)

        self.childrenChanged.emit(self)
        pass

    ##  \brief Removes all children and its children's children.
    def removeAllChildren(self):
        for child in self._children:
            child.removeAllChildren()
            self.removeChild(child)

        self.childrenChanged.emit(self)

    ##  \brief Get the list of direct children
    #   \returns List of children
    def getChildren(self):
        return self._children

    ##  \brief Get list of all children (including it's children children children etc.)
    #   \returns list ALl children in this 'tree'
    def getAllChildren(self):
        children = []
        children.extend(self._children)
        for child in self._children:
            children.extend(child.getAllChildren())
        return children

    ##  \brief Emitted whenever the list of children of this object or any child object changes.
    #   \param object The object that triggered the change.
    childrenChanged = Signal()

    ##  \brief Computes and returns the transformation from origin to local space
    #   \returns 4x4 transformation matrix
    def getGlobalTransformation(self):
        if(self._parent is None):
            return self._transformation
        else:
            global_transformation = deepcopy(self._transformation)
            global_transformation.preMultiply(self._parent.getGlobalTransformation())
            return global_transformation

    ##  \brief Returns the local transformation with respect to its parent. (from parent to local)
    #   \retuns transformation 4x4 (homogenous) matrix
    def getLocalTransformation(self):
        return self._transformation

    ##  \brief Sets the local transformation with respect to its parent. (from parent to local)
    #   \param transformation 4x4 (homogenous) matrix
    def setLocalTransformation(self, transformation):
        if self._locked:
            return

        self._transformation = transformation
        self._transformChanged()

    ##  \brief Rotate the scene object (and thus its children) by given amount
    def rotate(self, rotation):
        if self._locked:
            return

        rotMatrix = Matrix()
        rotMatrix.setByQuaternion(rotation)
        self._transformation.multiply(rotMatrix)
        self._transformChanged()

    def rotateByAngleAxis(self, angle, axis):
        if self._locked:
            return

        self._transformation.rotateByAxis(math.radians(angle), axis)
        self._transformChanged()

    ##  Scale the scene object (and thus its children) by given amount
    def scale(self, scale):
        self._transformation.scaleByFactor(scale)
        self._transformChanged()

    ##  Translate the scene object (and thus its children) by given amount.
    #   \param translation Vector(x,y,z).
    def translate(self, translation):
        if self._locked:
            return

        self._transformation.translate(translation)
        self._transformChanged()

    ##  Set
    def setPosition(self, position):
        if self._locked:
            return

        self._transformation.setByTranslation(position)
        self._transformChanged()

    def getPosition(self):
        pos = self._transformation.getData()
        return Vector(pos[0,3], pos[1,3], pos[2,3])

    def getGlobalPosition(self):
        pos = self.getGlobalTransformation().getData()
        return Vector(float(pos[0,3]), pos[1,3], pos[2,3])

    ##  Signal. Emitted whenever the transformation of this object or any child object changes.
    #   \param object The object that caused the change.
    transformationChanged = Signal()
    
    ##  Check if this node is at the bottom of the tree (and thus a leaf node).
    #   \returns True if its a leaf object, false otherwise.
    def isLeafNode(self):
        if len(self._children) == 0:
            return True
        return False

    ##  Can be overridden by child nodes if they need to perform special rendering.
    #   If you need to handle rendering in a special way, for example for tool handles,
    #   you can override this method and render the node. Return True to prevent the
    #   view from rendering any attached mesh data.
    #
    #   \param renderer The renderer object to use for rendering.
    #
    #   \return False if the view should render this node, True if we handle our own rendering.
    def render(self, renderer):
        return False

    ##  Get whether this SceneNode is locked, that is, its transformation relative to its parent should not change.
    def isLocked(self):
        return self._locked

    ##  Set whether this SceneNode is locked.
    #   \param lock True if this object should be locked, False if not.
    #   \sa isLocked
    def setLocked(self, lock):
        self._locked = lock

    ##  Get the bounding box of this node and its children.
    #
    #   Note that the AABB is calculated in a separate thread. This method will return an invalid (size 0) AABB
    #   while the calculation happens.
    def getBoundingBox(self):
        if self._aabb:
            return self._aabb

        if self._aabbJob:
            if self._aabbJob.isFinished():
                self._aabb = self._aabbJob.getResult()
                self._aabbJob = None
                return self._aabb
        else:
            self._resetAABB()

        return AxisAlignedBox()

    # TODO: This can probably be simplified to an enabled property or similar. Maybe combine with locked?
    def getSelectionMask(self):
        return self._selectionMask

    def setSelectionMask(self, mask):
        self._selectionMask = mask

    ##  private:

    def _transformChanged(self):
        self._resetAABB()
        self.transformationChanged.emit(self)

    def _resetAABB(self):
        self._aabb = None

        if self._aabbJob:
            self._aabbJob.cancel()

        self._aabbJob = _CalculateAABBJob(self)
        self._aabbJob.start()

##  Internal
#   Calculates the AABB of a node and its children.
class _CalculateAABBJob(Job):
    def __init__(self, node):
        super().__init__()
        self._node = node

    def run(self):
        aabb = None
        if self._node._mesh_data:
            aabb = self._node._mesh_data.getExtents(self._node.getGlobalTransformation())
        else:
            aabb = AxisAlignedBox()

        for child in self._node._children:
            aabb += child.getBoundingBox()

        self.setResult(aabb)
