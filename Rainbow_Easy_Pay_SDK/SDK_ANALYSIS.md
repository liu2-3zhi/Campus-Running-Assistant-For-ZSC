# 彩虹易支付SDK分析文档

## 概述
本文档详细分析Rainbow_Easy_Pay_SDK的实现，验证其与彩虹易支付平台对接的正确性。

## SDK结构分析

### 1. 核心文件
- `lib/EpayCore.class.php` - 核心SDK类
- `lib/epay.config.php` - 配置文件
- `epayapi.php` - 支付接口入口
- `notify_url.php` - 异步通知处理
- `return_url.php` - 同步返回处理
- `query.php` - 订单查询示例
- `refund.php` - 退款示例
- `index.php` - 测试页面

### 2. 配置文件分析 (epay.config.php)

#### 配置项说明
```php
$epay_config = [
    'apiurl' => 'http://pay.www.com/',  // 支付接口地址
    'pid' => '1000',                     // 商户ID
    'platform_public_key' => '...',      // 平台公钥（用于验签）
    'merchant_private_key' => '...',     // 商户私钥（用于签名）
];
```

**验证结果**: ✅ 配置结构正确
- 包含必需的四个配置项
- 使用RSA密钥对进行签名和验签
- 商户需要根据实际情况修改这些配置

### 3. 核心类分析 (EpayCore.class.php)

#### 3.1 签名算法
- **签名类型**: RSA (sign_type = 'RSA')
- **签名算法**: OPENSSL_ALGO_SHA256 (SHA256withRSA)
- **签名流程**:
  1. 将参数按键名排序 (ksort)
  2. 拼接成 key1=value1&key2=value2 格式
  3. 使用商户私钥进行RSA签名
  4. Base64编码签名结果

**验证结果**: ✅ 签名算法实现正确
- 符合标准的RSA签名流程
- 正确处理了空值和特殊参数（sign, sign_type）

#### 3.2 验签算法
- 使用平台公钥验证回调数据
- 包含时间戳验证（300秒有效期）
- 防止重放攻击

**验证结果**: ✅ 验签逻辑安全可靠
```php
// 时间戳验证，防止重放攻击
if(empty($arr['timestamp']) || abs(time() - $arr['timestamp']) > 300) 
    return false;
```

#### 3.3 核心方法

##### pagePay() - 页面跳转支付
- **用途**: 生成HTML表单自动提交到支付页面
- **API端点**: `/api/pay/submit`
- **方法**: POST
- **验证结果**: ✅ 实现正确

##### getPayLink() - 获取支付链接
- **用途**: 生成支付URL（适用于扫码支付）
- **API端点**: `/api/pay/submit`
- **方法**: GET
- **验证结果**: ✅ 实现正确

##### apiPay() - API接口支付
- **用途**: 通过API创建订单
- **API端点**: `/api/pay/create`
- **方法**: POST
- **验证结果**: ✅ 实现正确

##### queryOrder() - 查询订单
- **用途**: 查询订单支付状态
- **API端点**: `/api/pay/query`
- **参数**: trade_no (平台订单号)
- **验证结果**: ✅ 实现正确

##### refund() - 订单退款
- **用途**: 发起退款请求
- **API端点**: `/api/pay/refund`
- **参数**: 
  - trade_no: 平台订单号
  - money: 退款金额
  - out_refund_no: 商户退款单号
- **验证结果**: ✅ 实现正确

##### orderStatus() - 简易订单状态查询
- **用途**: 快速查询订单是否支付成功
- **返回**: true/false
- **验证结果**: ✅ 实现正确

### 4. API端点汇总

| 功能 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 发起支付 | /api/pay/submit | POST/GET | 页面跳转或获取链接 |
| API支付 | /api/pay/create | POST | API方式创建订单 |
| 查询订单 | /api/pay/query | POST | 查询订单详情 |
| 订单退款 | /api/pay/refund | POST | 发起退款 |

**验证结果**: ✅ API端点设计合理，符合RESTful风格

### 5. 回调处理分析

#### 5.1 异步通知 (notify_url.php)
- **请求方式**: GET
- **验证流程**:
  1. 调用 `verify()` 方法验签
  2. 检查 `trade_status` 状态
  3. 处理业务逻辑
  4. 返回 "success" 或 "fail"

**关键参数**:
- out_trade_no: 商户订单号
- trade_no: 平台交易号
- trade_status: 交易状态 (TRADE_SUCCESS)
- type: 支付方式
- money: 支付金额

**验证结果**: ✅ 异步通知处理正确
- 正确实现了验签逻辑
- 包含必要的业务处理占位
- 返回格式符合规范

#### 5.2 同步返回 (return_url.php)
- **请求方式**: GET
- **用途**: 用户支付完成后跳转显示
- **验证流程**: 与异步通知相同

**验证结果**: ✅ 同步返回处理正确

### 6. 支付方式支持

SDK支持以下支付方式（type参数）:
- alipay: 支付宝
- wxpay: 微信支付
- qqpay: QQ钱包
- bank: 云闪付
- jdpay: 京东支付

**验证结果**: ✅ 支付方式齐全

### 7. 安全性分析

#### 7.1 签名安全
- ✅ 使用RSA非对称加密
- ✅ 密钥长度2048位，安全强度高
- ✅ 使用SHA256算法，防止碰撞攻击

#### 7.2 防重放攻击
- ✅ 时间戳验证（300秒有效期）
- ✅ 每次请求包含唯一的timestamp

#### 7.3 数据完整性
- ✅ 所有参数参与签名
- ✅ 签名验证失败立即返回

#### 7.4 HTTPS支持
- ⚠️ SDK本身支持HTTPS
- ⚠️ 配置文件中使用HTTP，建议修改为HTTPS

### 8. 潜在问题和建议

#### 8.1 配置安全
**问题**: 私钥直接写在配置文件中
**建议**: 
- 将私钥存储在环境变量或加密文件中
- 添加文件权限保护（chmod 600）

#### 8.2 错误处理
**问题**: 部分异常处理不够详细
**建议**: 
- 增加日志记录功能
- 详细记录签名失败、网络错误等异常

#### 8.3 配置验证
**建议**: 
- 添加配置项验证功能
- 检查API地址、PID等是否正确配置

#### 8.4 URL配置
**当前**: notify_url和return_url硬编码在示例中
**建议**: 将URL配置移到config文件中

### 9. 与Python后端集成建议

#### 9.1 Python SDK实现要点
```python
# 需要实现的核心功能
1. RSA签名和验签（使用cryptography库）
2. 参数排序和拼接
3. HTTP请求封装
4. 回调验证中间件
```

#### 9.2 集成步骤
1. 在main.py中实现EpayCore的Python版本
2. 创建配置管理（从config.ini读取）
3. 实现以下API端点：
   - /api/payment/create - 创建支付订单
   - /api/payment/query - 查询订单状态
   - /api/payment/refund - 发起退款
   - /api/payment/notify - 接收异步通知
   - /api/payment/return - 处理同步返回

#### 9.3 数据库设计建议
建议创建订单表存储：
- 商户订单号 (out_trade_no)
- 平台交易号 (trade_no)
- 支付金额 (money)
- 支付状态 (status)
- 支付方式 (type)
- 用户名 (username)
- 创建时间、支付时间等

### 10. 测试建议

#### 10.1 单元测试
- [ ] 签名算法测试
- [ ] 验签算法测试
- [ ] 参数拼接测试
- [ ] 时间戳验证测试

#### 10.2 集成测试
- [ ] 创建订单测试（小额如0.01元）
- [ ] 查询订单测试
- [ ] 退款测试
- [ ] 回调验证测试

#### 10.3 安全测试
- [ ] 签名篡改测试
- [ ] 重放攻击测试
- [ ] 参数注入测试

## 结论

**总体评价**: ✅ SDK实现质量良好，可以正常使用

**核心优势**:
1. 签名算法实现正确，使用RSA+SHA256，安全性高
2. API设计合理，覆盖支付、查询、退款等核心功能
3. 回调验证逻辑完善，包含时间戳验证
4. 代码结构清晰，易于理解和维护

**需要改进**:
1. 建议使用HTTPS替代HTTP
2. 增强错误处理和日志记录
3. 密钥管理需要加强安全性
4. URL配置应该集中管理

**集成到Python后端的可行性**: ✅ 完全可行
- SDK逻辑清晰，可以直接翻译为Python代码
- API端点明确，易于实现
- 签名算法标准，Python有成熟的cryptography库支持

---
*分析完成日期: 2025-12-10*
*分析人: Copilot Agent*
