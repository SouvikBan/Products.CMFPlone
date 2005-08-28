#
# Test the browserDefault script
#

import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Acquisition import aq_base
from Testing import ZopeTestCase
from Products.CMFPlone.tests import PloneTestCase
from Products.CMFPlone.tests.PloneTestCase import FunctionalTestCase
from Products.CMFPlone.tests.PloneTestCase import default_user
from Products.CMFPlone.tests.PloneTestCase import default_password
from Products.CMFPlone.tests import dummy
import difflib
import re

from Products.CMFPlone.utils import _createObjectByType
from Products.CMFPlone.PloneFolder import ReplaceableWrapper

RE_REMOVE_DOCCONT = re.compile('href="http://.*?#documentContent"')
RE_REMOVE_NAVTREE = re.compile('href="http://.*?#portlet-navigation-tree"')

class TestPloneToolBrowserDefault(FunctionalTestCase):
    """Test the PloneTool's browserDefault() method in various use cases.
    This class basically tests the functionality when items have default pages
    and actions that resolve to actual objects. The cases where a default_page
    may be set to a non-existing object are covered by TestDefaultPage below.
    """

    def afterSetUp(self):
        self.setRoles(['Manager'])
        self.basic_auth = '%s:%s' % (default_user, default_password)

        _createObjectByType('Folder',       self.portal, 'atctfolder')
        _createObjectByType('CMF Folder',   self.portal, 'cmffolder')
        _createObjectByType('Document',     self.portal, 'atctdocument')
        _createObjectByType('CMF Document', self.portal, 'cmfdocument')
        _createObjectByType('File',         self.portal, 'atctfile')
        _createObjectByType('CMF File',     self.portal, 'cmffile')

        self.putils = self.portal.plone_utils

    def compareLayoutVsView(self, obj, path="", viewaction=None):
        if viewaction is None:
            if hasattr(aq_base(obj), 'getLayout'):
                viewaction = obj.getLayout()
            else:
                viewaction = obj.getTypeInfo().getActionById('view')

        resolved = getattr(obj, viewaction)()
        base_path = obj.absolute_url(1)

        response = self.publish(base_path+path, self.basic_auth)
        body = response.getBody()

        # request/ACTUAL_URL is fubar in tests, remove lines that depend on it
        resolved = RE_REMOVE_DOCCONT.sub('', resolved)
        resolved = RE_REMOVE_NAVTREE.sub('', resolved)
        body = RE_REMOVE_DOCCONT.sub('', body)
        body = RE_REMOVE_NAVTREE.sub('', body)

        if not body:
            self.fail('No body in response')

        if not body == resolved:
            diff = difflib.unified_diff(body.split("\n"),
                                        resolved.split("\n"))
            self.fail("\n".join([line for line in diff]))

        return response

    def compareLayoutVsCall(self, obj):
        if hasattr(aq_base(obj), 'getLayout'):
            viewaction = obj.getLayout()
        else:
            viewaction = obj.getTypeInfo().getActionById('view')

        base_path = obj.absolute_url(1)
        viewed = getattr(obj, viewaction)()
        called = obj()

        # request/ACTUAL_URL is fubar in tests, remove line that depends on it
        called = RE_REMOVE_DOCCONT.sub('', called)
        viewed = RE_REMOVE_DOCCONT.sub('', viewed)

        if not called or not viewed:
            self.fail('No body in response')

        if not viewed == called:
            diff = difflib.unified_diff(viewed.split("\n"),
                                        called.split("\n"))
            self.fail("\n".join([line for line in diff]))

    # Folders with IBrowserDefault - default page, index_html, global default

    def testBrowserDefaultMixinFolderDefaultPage(self):
        self.portal.atctfolder.invokeFactory('Document', 'default')
        self.portal.atctfolder.setDefaultPage('default')
        self.assertEqual(self.putils.browserDefault(self.portal.atctfolder),
                         (self.portal.atctfolder, ['default'],))

    def testBrowserDefaultMixinFolderIndexHtml(self):
        self.portal.atctfolder.invokeFactory('Document', 'default')
        self.portal.atctfolder.setDefaultPage('default')
        # index_html should always win - it's an explicit override!
        self.portal.atctfolder.invokeFactory('Document', 'index_html')
        self.assertEqual(self.putils.browserDefault(self.portal.atctfolder),
                         (self.portal.atctfolder, ['index_html'],))

    def testBrowserDefaultMixinFolderGlobalDefaultPage(self):
        self.portal.portal_properties.site_properties.manage_changeProperties(default_page = ['foo'])
        self.portal.atctfolder.invokeFactory('Document', 'foo')
        self.assertEqual(self.putils.browserDefault(self.portal.atctfolder),
                         (self.portal.atctfolder, ['foo']))

    # Folders without IBrowserDefault - index_html, default_page, global default

    def testNonBrowserDefaultMixinFolderDefaultPageProperty(self):
        self.portal.cmffolder.invokeFactory('Document', 'foo')
        self.portal.cmffolder.manage_addProperty('default_page', 'foo', 'string')
        self.assertEqual(self.putils.browserDefault(self.portal.cmffolder),
                         (self.portal.cmffolder, ['foo'],))

    def testNonBrowserDefaultMixinFolderIndexHtml(self):
        self.portal.cmffolder.manage_addProperty('default_page', 'foo', 'string')
        self.portal.cmffolder.invokeFactory('Document', 'foo')
        # Again, index_html always wins!
        self.portal.cmffolder.invokeFactory('Document', 'index_html')
        self.assertEqual(self.putils.browserDefault(self.portal.cmffolder),
                         (self.portal.cmffolder, ['index_html'],))

    def testNonBrowserDefaultMixinFolderGlobalDefaultPage(self):
        self.portal.portal_properties.site_properties.manage_changeProperties(default_page = ['foo'])
        self.portal.cmffolder.invokeFactory('Document', 'foo')
        self.assertEqual(self.putils.browserDefault(self.portal.cmffolder),
                         (self.portal.cmffolder, ['foo']))

    # folderlisting action resolution (for folders without default pages)

    def testNonBrowserDefaultMixinFolderFolderlistingAction(self):
        viewAction = self.portal.portal_types['CMF Folder'].getActionById('folderlisting')
        self.assertEqual(self.putils.browserDefault(self.portal.cmffolder),
                         (self.portal.cmffolder, [viewAction]))

    # View action resolution (last fallback)

    def testViewMethodWithBrowserDefaultMixinGetsSelectedLayout(self):
        self.compareLayoutVsView(self.portal.atctdocument, path="/view")

    def testViewMethodWithoutBrowserDefaultMixinGetsViewAction(self):
        viewAction = self.portal.portal_types['CMF Document'].getActionById('view')
        obj = self.portal.cmfdocument
        self.compareLayoutVsView(self.portal.cmfdocument, path="/view",
                                 viewaction=viewAction)

    def testCallWithBrowserDefaultMixinGetsSelectedLayout(self):
        self.compareLayoutVsView(self.portal.atctdocument, path="")

    def testCallWithoutBrowserDefaultMixinGetsViewAction(self):
        viewAction = self.portal.portal_types['CMF Document'].getActionById('view')
        obj = self.portal.cmfdocument
        self.compareLayoutVsView(self.portal.cmfdocument, path="",
                                 viewaction=viewAction)

    # Dump data from file objects (via index_html), but get template when explicitly called

    def testBrowserDefaultMixinFileViewMethodGetsTemplate(self):
        self.compareLayoutVsView(self.portal.atctfile, path="/view")

    def testNonBrowserDefaultMixinFileViewMethodGetsTemplateFromViewAction(self):
        self.compareLayoutVsView(self.portal.cmffile, path="/view")

    def testBrowserDefaultMixinFileDumpsContent(self):
        response = self.publish(self.portal.atctfile.absolute_url(1), self.basic_auth)
        self.failUnlessEqual(response.getBody(), str(self.portal.atctfile.getFile()))

    def testNonBrowserDefaultMixinFileDumpsContent(self):
        response = self.publish(self.portal.cmffile.absolute_url(1), self.basic_auth)
        self.failUnlessEqual(response.getBody(), str(self.portal.cmffile.data))


    # Ensure index_html acquisition and replaceablewrapper

    def testIndexHtmlNotAcquired(self):
        self.portal.atctfolder.invokeFactory('Document', 'index_html')
        self.portal.atctfolder.invokeFactory('Folder', 'subfolder')
        layout = self.portal.atctfolder.getLayout()
        self.assertEqual(self.putils.browserDefault(self.portal.atctfolder.subfolder),
                         (self.portal.atctfolder.subfolder, [layout]))

    def testIndexHtmlReplaceableWrapper(self):
        self.portal.atctdocument.index_html = ReplaceableWrapper(None)
        layout = self.portal.atctdocument.getLayout()
        self.assertEqual(self.putils.browserDefault(self.portal.atctdocument),
                         (self.portal.atctdocument, [layout]))

    # Test behaviour of __call__

    def testCallDocumentGivesTemplate(self):
        self.compareLayoutVsCall(self.portal.atctdocument)

    def testCallFolderWithoutDefaultPageGivesTemplate(self):
        self.compareLayoutVsCall(self.portal.atctfolder)

    def testCallFolderWithDefaultPageGivesTemplate(self):
        self.portal.atctfolder.invokeFactory('Document', 'doc')
        self.portal.atctfolder.setDefaultPage('doc')
        self.compareLayoutVsCall(self.portal.atctfolder)

    def testCallFileGivesTemplate(self):
        self.portal.atctfolder.invokeFactory('File', 'f1')
        self.compareLayoutVsCall(self.portal.atctfolder.f1)

    # Tests for strange bugs...

    def testReselectingDefaultLayoutAfterDefaultPageWorks(self):
        defaultLayout = self.portal.atctfolder.getDefaultLayout()
        self.portal.atctfolder.invokeFactory('Document', 'default')
        self.portal.atctfolder.setDefaultPage('default')
        self.portal.atctfolder.setLayout(defaultLayout)
        self.assertEqual(self.portal.atctfolder.getDefaultPage(), None)
        self.assertEqual(self.portal.atctfolder.defaultView(), defaultLayout)

class TestDefaultPage(PloneTestCase.PloneTestCase):
    """Test the default_page functionality in more detail
    """

    def afterSetUp(self):
        self.ob = dummy.DefaultPage()
        sp = self.portal.portal_properties.site_properties
        self.default = sp.getProperty('default_page', [])

    def getDefault(self):
        return self.portal.plone_utils.browserDefault(self.ob)

    def testDefaultPageSetting(self):
        self.assertEquals(self.default, ('index_html', 'index.html',
                                         'index.htm', 'FrontPage'))

    def testDefaultPageStringExist(self):
        # Test for https://plone.org/collector/2671
        self.ob.keys = [] # Make sure 'index_html' fake key doesn't win
        self.ob.set_default('test', 1)
        self.assertEquals(self.getDefault(), (self.ob, ['test']))

    def testDefaultPageStringNotExist(self):
        # Test for https://plone.org/collector/2671
        self.ob.set_default('test', 0)
        self.assertEquals(self.getDefault(), (self.ob, ['index_html']))

    def testDefaultPageSequenceExist(self):
        # Test for https://plone.org/collector/2671
        self.ob.set_default(['test'], 1)
        self.assertEquals(self.getDefault(), (self.ob, ['test']))

    def testDefaultPageSequenceNotExist(self):
        # Test for https://plone.org/collector/2671
        self.ob.set_default(['test'], 0)
        self.assertEquals(self.getDefault(), (self.ob, ['index_html']))
        self.ob.keys = ['index.html']
        self.assertEquals(self.getDefault(), (self.ob, ['index.html']))
        self.ob.keys = ['index.htm']
        self.assertEquals(self.getDefault(), (self.ob, ['index.htm']))
        self.ob.keys = ['FrontPage']
        self.assertEquals(self.getDefault(), (self.ob, ['FrontPage']))

    def testBrowserDefaultPage(self):
        # Test assumes ATContentTypes + BrowserDefaultMixin
        self.folder.invokeFactory('Document', 'd1', title='document 1')
        self.folder.setDefaultPage('d1')
        self.assertEquals(self.portal.plone_utils.browserDefault(self.folder),
                            (self.folder, ['d1']))

class TestPortalBrowserDefault(PloneTestCase.PloneTestCase):
    """Test the BrowserDefaultMixin as implemented by the root portal object
    """
    
    def afterSetUp(self):
        self.setRoles(['Manager'])
        
        # Make sure we have the front page; the portal generator should take 
        # care of this, but let's not be dependent on that in the test
        if not 'front-page' in self.portal.objectIds():
            self.portal.invokeFactory('Document', 'front-page',
                                      title = 'Welcome to Plone')
        self.portal.setDefaultPage('front-page')
    
        # Also make sure we have folder_listing and news_listing as templates
        self.portal.getTypeInfo().manage_changeProperties(view_methods =
                                        ['folder_listing', 'news_listing'],
                                        default_view = 'folder_listing')
            
    def testCall(self):
        self.portal.setLayout('news_listing')
        resolved = self.portal()
        target = self.portal.unrestrictedTraverse('news_listing')()
        self.assertEqual(resolved, target)
            
    def testDefaultViews(self):
        self.assertEqual(self.portal.getLayout(), 'folder_listing')
        self.assertEqual(self.portal.getDefaultPage(), 'front-page')
        self.assertEqual(self.portal.defaultView(), 'front-page')
        self.assertEqual(self.portal.getDefaultLayout(), 'folder_listing')
        layoutKeys = [v[0] for v in self.portal.getAvailableLayouts()]
        self.failUnless('folder_listing' in layoutKeys)
        self.failUnless('news_listing' in layoutKeys)
        self.assertEqual(self.portal.__browser_default__(None), (self.portal, ['front-page',]))
        
    def testCanSetLayout(self):
        self.failUnless(self.portal.canSetLayout())
        self.portal.manage_permission("Modify view template", [], 0)
        self.failIf(self.portal.canSetLayout()) # Not permitted
    
    def testSetLayout(self):
        self.portal.setLayout('news_listing')
        self.assertEqual(self.portal.getLayout(), 'news_listing')
        self.assertEqual(self.portal.getDefaultPage(), None)
        self.assertEqual(self.portal.defaultView(), 'news_listing')
        self.assertEqual(self.portal.getDefaultLayout(), 'folder_listing')
        layoutKeys = [v[0] for v in self.portal.getAvailableLayouts()]
        self.failUnless('folder_listing' in layoutKeys)
        self.failUnless('news_listing' in layoutKeys)
        
        view = self.portal.view()
        browserDefault = self.portal.__browser_default__(None)[1][0]
        browserDefaultResolved = self.portal.unrestrictedTraverse(browserDefault)()
        template = self.portal.defaultView()
        templateResolved = self.portal.unrestrictedTraverse(template)()
        
        self.assertEqual(view, browserDefaultResolved)
        self.assertEqual(view, templateResolved)
        
    def testCanSetDefaultPage(self):
        self.failUnless(self.portal.canSetDefaultPage())
        self.portal.invokeFactory('Document', 'ad')
        self.failIf(self.portal.ad.canSetDefaultPage()) # Not folderish
        self.portal.manage_permission("Modify view template", [], 0)
        self.failIf(self.portal.canSetDefaultPage()) # Not permitted
        
    def testSetDefaultPage(self):
        self.portal.invokeFactory('Document', 'ad')
        self.portal.setDefaultPage('ad')
        self.assertEqual(self.portal.getDefaultPage(), 'ad')
        self.assertEqual(self.portal.defaultView(), 'ad')
        self.assertEqual(self.portal.__browser_default__(None), (self.portal, ['ad',]))

        # still have layout settings
        self.assertEqual(self.portal.getLayout(), 'folder_listing')
        self.assertEqual(self.portal.getDefaultLayout(), 'folder_listing')
        layoutKeys = [v[0] for v in self.portal.getAvailableLayouts()]
        self.failUnless('folder_listing' in layoutKeys)
        self.failUnless('news_listing' in layoutKeys)

    def testSetDefaultPageUpdatesCatalog(self):
        # Ensure that Default page changes update the catalog
        cat = self.portal.portal_catalog
        self.portal.invokeFactory('Document', 'ad')
        self.portal.invokeFactory('Document', 'other')
        self.assertEqual(len(cat(getId=['ad','other'],is_default_page=True)), 0)
        self.portal.setDefaultPage('ad')
        self.assertEqual(len(cat(getId='ad',is_default_page=True)), 1)
        self.portal.setDefaultPage('other')
        self.assertEqual(len(cat(getId='other',is_default_page=True)), 1)
        self.assertEqual(len(cat(getId='ad',is_default_page=True)), 0)
        self.portal.setDefaultPage(None)
        self.assertEqual(len(cat(getId=['ad','other'],is_default_page=True)), 0)

    def testSetLayoutUnsetsDefaultPage(self):
        self.portal.invokeFactory('Document', 'ad')
        self.portal.setDefaultPage('ad')
        self.assertEqual(self.portal.getDefaultPage(), 'ad')
        self.assertEqual(self.portal.defaultView(), 'ad')
        self.portal.setLayout('folder_listing')
        self.assertEqual(self.portal.getDefaultPage(), None)
        self.assertEqual(self.portal.defaultView(), 'folder_listing')

        view = self.portal.view()
        browserDefault = self.portal.__browser_default__(None)[1][0]
        browserDefaultResolved = self.portal.unrestrictedTraverse(browserDefault)()
        template = self.portal.defaultView()
        templateResolved = self.portal.unrestrictedTraverse(template)()

        self.assertEqual(view, browserDefaultResolved)
        self.assertEqual(view, templateResolved)

    def testMissingTemplatesIgnored(self):
        self.portal.getTypeInfo().manage_changeProperties(view_methods = ['folder_listing', 'foo'])
        views = [v[0] for v in self.portal.getAvailableLayouts()]
        self.failUnless(views == ['folder_listing'])

    def testMissingPageIgnored(self):
        self.portal.setDefaultPage('inexistent')
        self.assertEqual(self.portal.getDefaultPage(), None)
        self.assertEqual(self.portal.defaultView(), 'folder_listing')
        self.assertEqual(self.portal.__browser_default__(None), (self.portal, ['folder_listing',]))

    def testTemplateTitles(self):
        views = [v for v in self.portal.getAvailableLayouts() if v[0] == 'folder_listing']
        self.assertEqual(views[0][1], 'Standard view')
        try:
            folderListing = self.portal.unrestrictedTraverse('folder_listing')
            folderListing.title = 'foo'
            views = [v for v in self.portal.getAvailableLayouts() if v[0] == 'folder_listing']
            self.assertEqual(views[0][1], 'foo')
        finally:
            # Restore title to avoid side-effects
            folderListing.title = 'Standard view'


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestPloneToolBrowserDefault))
    suite.addTest(makeSuite(TestDefaultPage))
    suite.addTest(makeSuite(TestPortalBrowserDefault))
    return suite

if __name__ == '__main__':
    framework()
