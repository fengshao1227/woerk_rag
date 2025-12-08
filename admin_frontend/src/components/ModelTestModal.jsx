import { useState } from 'react';
import { Modal, Form, Input, InputNumber, Button, Spin, Card, message, Typography, Statistic, Row, Col } from 'antd';
import { SendOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { testAPI } from '../services/api';

const { TextArea } = Input;
const { Paragraph } = Typography;

export default function ModelTestModal({ visible, model, onClose }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleTest = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      setResult(null);

      const response = await testAPI.testModel({
        model_id: model.id,
        prompt: values.prompt,
        temperature: values.temperature,
        max_tokens: values.max_tokens
      });

      setResult(response.data);
    } catch (error) {
      message.error('测试失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    form.resetFields();
    setResult(null);
    onClose();
  };

  return (
    <Modal
      title={`测试模型: ${model?.display_name || ''}`}
      open={visible}
      onCancel={handleClose}
      width={800}
      footer={null}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          prompt: '你好，请用一句话介绍自己。',
          temperature: model?.temperature || 0.7,
          max_tokens: model?.max_tokens || 1024
        }}
      >
        <Form.Item
          name="prompt"
          label="测试提示词"
          rules={[{ required: true, message: '请输入测试提示词' }]}
        >
          <TextArea rows={4} placeholder="输入测试提示词..." />
        </Form.Item>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="temperature" label="Temperature">
              <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="max_tokens" label="Max Tokens">
              <InputNumber min={1} max={32000} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item>
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleTest}
            loading={loading}
            block
          >
            发送测试
          </Button>
        </Form.Item>
      </Form>

      {loading && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16, color: '#666' }}>正在等待模型响应...</div>
        </div>
      )}

      {result && (
        <Card
          title={
            <span>
              {result.success
                ? <><CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />测试成功</>
                : <><CloseCircleOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />测试失败</>
              }
            </span>
          }
          style={{ marginTop: 16 }}
        >
          {result.success ? (
            <>
              <Paragraph
                copyable
                style={{
                  background: '#f5f5f5',
                  padding: 16,
                  borderRadius: 8,
                  maxHeight: 300,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap'
                }}
              >
                {result.response}
              </Paragraph>

              <Row gutter={16} style={{ marginTop: 16 }}>
                <Col span={6}>
                  <Statistic
                    title="Prompt Tokens"
                    value={result.usage?.prompt_tokens || 0}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="Completion Tokens"
                    value={result.usage?.completion_tokens || 0}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="总计 Tokens"
                    value={result.usage?.total_tokens || 0}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="响应时间"
                    value={result.request_time?.toFixed(2) || 0}
                    suffix="秒"
                    valueStyle={{ fontSize: 16 }}
                  />
                </Col>
              </Row>
            </>
          ) : (
            <Paragraph type="danger">
              {result.error}
            </Paragraph>
          )}
        </Card>
      )}
    </Modal>
  );
}
