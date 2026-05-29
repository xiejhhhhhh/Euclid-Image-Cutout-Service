#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康检查和首页路由
"""

import logging
from flask import Blueprint, render_template, jsonify

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


@health_bp.route('/')
def index():
    """首页"""
    return render_template('index_Euclid_legacy.html')


@health_bp.route("/health")
def api_health():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'service': 'euclid-cutout-flask',
        'version': '1.0.0'
    })
