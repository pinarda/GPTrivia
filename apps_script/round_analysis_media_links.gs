function getSlideLinkedMediaUrls(presentationId, slideObjectId) {
  var presentation = SlidesApp.openById(presentationId);
  var slides = presentation.getSlides();
  var targetSlide = null;
  for (var i = 0; i < slides.length; i++) {
    if (slides[i].getObjectId() === slideObjectId) {
      targetSlide = slides[i];
      break;
    }
  }
  if (!targetSlide) {
    return [];
  }

  var results = [];

  function safeGetLinkMetadata(pageElement) {
    var link = null;
    try {
      link = pageElement.getLink();
    } catch (err) {
      link = null;
    }
    if (!link) {
      return {
        has_link: false,
        link_type: '',
        linked_url: '',
      };
    }

    var linkType = '';
    var linkedUrl = '';
    try {
      linkType = String(link.getLinkType() || '');
    } catch (err) {
      linkType = '';
    }
    try {
      linkedUrl = String(link.getUrl() || '');
    } catch (err) {
      linkedUrl = '';
    }

    return {
      has_link: true,
      link_type: linkType,
      linked_url: linkedUrl,
    };
  }

  function safeGetDimension(pageElement, axis) {
    try {
      if (axis === 'width') {
        return Number(pageElement.getWidth()) || 0;
      }
      return Number(pageElement.getHeight()) || 0;
    } catch (err) {
      return 0;
    }
  }

  function safeGetTitle(pageElement) {
    try {
      return String(pageElement.getTitle() || '');
    } catch (err) {
      return '';
    }
  }

  function safeGetDescription(pageElement) {
    try {
      return String(pageElement.getDescription() || '');
    } catch (err) {
      return '';
    }
  }

  function safeGetSourceUrl(imageElement) {
    try {
      return String(imageElement.getSourceUrl() || '');
    } catch (err) {
      return '';
    }
  }

  function pushLinkedElement(pageElement, linkedKind) {
    if (!pageElement) {
      return;
    }
    var linkMetadata = safeGetLinkMetadata(pageElement);
    if (!linkMetadata.has_link || !linkMetadata.linked_url) {
      return;
    }
    results.push({
      element_id: pageElement.getObjectId(),
      linked_url: linkMetadata.linked_url,
      linked_kind: linkedKind || '',
    });
  }

  function walkPageElements(pageElements) {
    for (var i = 0; i < pageElements.length; i++) {
      var element = pageElements[i];
      var elementType = element.getPageElementType();
      if (elementType === SlidesApp.PageElementType.GROUP) {
        walkPageElements(element.asGroup().getChildren());
        continue;
      }
      if (elementType === SlidesApp.PageElementType.IMAGE) {
        pushLinkedElement(element.asImage(), 'audio');
        continue;
      }
      if (elementType === SlidesApp.PageElementType.VIDEO) {
        pushLinkedElement(element.asVideo(), 'video');
      }
    }
  }

  walkPageElements(targetSlide.getPageElements());
  return results;
}

function debugSlideLinkedMediaUrls(presentationId, slideObjectId) {
  var presentation = SlidesApp.openById(presentationId);
  var slides = presentation.getSlides();
  var targetSlide = null;
  for (var i = 0; i < slides.length; i++) {
    if (slides[i].getObjectId() === slideObjectId) {
      targetSlide = slides[i];
      break;
    }
  }
  if (!targetSlide) {
    return [];
  }

  var results = [];

  function safeGetLinkMetadata(pageElement) {
    var link = null;
    try {
      link = pageElement.getLink();
    } catch (err) {
      link = null;
    }
    if (!link) {
      return {
        has_link: false,
        link_type: '',
        linked_url: '',
      };
    }

    var linkType = '';
    var linkedUrl = '';
    try {
      linkType = String(link.getLinkType() || '');
    } catch (err) {
      linkType = '';
    }
    try {
      linkedUrl = String(link.getUrl() || '');
    } catch (err) {
      linkedUrl = '';
    }

    return {
      has_link: true,
      link_type: linkType,
      linked_url: linkedUrl,
    };
  }

  function safeGetDimension(pageElement, axis) {
    try {
      if (axis === 'width') {
        return Number(pageElement.getWidth()) || 0;
      }
      return Number(pageElement.getHeight()) || 0;
    } catch (err) {
      return 0;
    }
  }

  function safeGetTitle(pageElement) {
    try {
      return String(pageElement.getTitle() || '');
    } catch (err) {
      return '';
    }
  }

  function safeGetDescription(pageElement) {
    try {
      return String(pageElement.getDescription() || '');
    } catch (err) {
      return '';
    }
  }

  function safeGetSourceUrl(imageElement) {
    try {
      return String(imageElement.getSourceUrl() || '');
    } catch (err) {
      return '';
    }
  }

  function pushDebugElement(pageElement, elementTypeLabel) {
    if (!pageElement) {
      return;
    }

    var linkMetadata = safeGetLinkMetadata(pageElement);
    var row = {
      element_id: pageElement.getObjectId(),
      element_type: elementTypeLabel,
      title: safeGetTitle(pageElement),
      description: safeGetDescription(pageElement),
      width: safeGetDimension(pageElement, 'width'),
      height: safeGetDimension(pageElement, 'height'),
      has_link: linkMetadata.has_link,
      link_type: linkMetadata.link_type,
      linked_url: linkMetadata.linked_url,
      source_url: '',
    };

    if (elementTypeLabel === 'IMAGE') {
      row.source_url = safeGetSourceUrl(pageElement);
    }

    results.push(row);
  }

  function walkPageElements(pageElements) {
    for (var i = 0; i < pageElements.length; i++) {
      var element = pageElements[i];
      var elementType = element.getPageElementType();
      if (elementType === SlidesApp.PageElementType.GROUP) {
        walkPageElements(element.asGroup().getChildren());
        continue;
      }
      if (elementType === SlidesApp.PageElementType.IMAGE) {
        pushDebugElement(element.asImage(), 'IMAGE');
        continue;
      }
      if (elementType === SlidesApp.PageElementType.VIDEO) {
        pushDebugElement(element.asVideo(), 'VIDEO');
      }
    }
  }

  walkPageElements(targetSlide.getPageElements());
  return results;
}

function debugSlidePageElements(presentationId, slideObjectId) {
  var presentation = SlidesApp.openById(presentationId);
  var slides = presentation.getSlides();
  var targetSlide = null;
  var availableSlideIds = [];
  for (var i = 0; i < slides.length; i++) {
    var currentId = slides[i].getObjectId();
    availableSlideIds.push(currentId);
    if (currentId === slideObjectId) {
      targetSlide = slides[i];
    }
  }

  var debugPayload = {
    requested_slide_id: String(slideObjectId || ''),
    found_slide: !!targetSlide,
    available_slide_ids: availableSlideIds,
    page_elements: [],
  };

  if (!targetSlide) {
    return debugPayload;
  }

  function safeGetTitle(pageElement) {
    try {
      return String(pageElement.getTitle() || '');
    } catch (err) {
      return '';
    }
  }

  function safeGetDescription(pageElement) {
    try {
      return String(pageElement.getDescription() || '');
    } catch (err) {
      return '';
    }
  }

  function safeGetDimension(pageElement, axis) {
    try {
      if (axis === 'width') {
        return Number(pageElement.getWidth()) || 0;
      }
      return Number(pageElement.getHeight()) || 0;
    } catch (err) {
      return 0;
    }
  }

  function safeGetLinkMetadata(pageElement) {
    var link = null;
    try {
      link = pageElement.getLink();
    } catch (err) {
      link = null;
    }
    if (!link) {
      return {
        has_link: false,
        link_type: '',
        linked_url: '',
      };
    }

    var linkType = '';
    var linkedUrl = '';
    try {
      linkType = String(link.getLinkType() || '');
    } catch (err) {
      linkType = '';
    }
    try {
      linkedUrl = String(link.getUrl() || '');
    } catch (err) {
      linkedUrl = '';
    }

    return {
      has_link: true,
      link_type: linkType,
      linked_url: linkedUrl,
    };
  }

  function safeGetSourceUrl(imageElement) {
    try {
      return String(imageElement.getSourceUrl() || '');
    } catch (err) {
      return '';
    }
  }

  function walkPageElements(pageElements, parentGroupId) {
    for (var i = 0; i < pageElements.length; i++) {
      var element = pageElements[i];
      var elementType = String(element.getPageElementType() || '');
      var linkMetadata = safeGetLinkMetadata(element);
      var row = {
        element_id: element.getObjectId(),
        parent_group_id: parentGroupId || '',
        element_type: elementType,
        title: safeGetTitle(element),
        description: safeGetDescription(element),
        width: safeGetDimension(element, 'width'),
        height: safeGetDimension(element, 'height'),
        has_link: linkMetadata.has_link,
        link_type: linkMetadata.link_type,
        linked_url: linkMetadata.linked_url,
        source_url: '',
      };

      if (elementType === 'IMAGE') {
        row.source_url = safeGetSourceUrl(element.asImage());
      }

      debugPayload.page_elements.push(row);

      if (elementType === 'GROUP') {
        walkPageElements(element.asGroup().getChildren(), element.getObjectId());
      }
    }
  }

  walkPageElements(targetSlide.getPageElements(), '');
  return debugPayload;
}
