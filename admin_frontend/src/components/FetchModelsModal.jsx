import { useState, useEffect } from 'react';
import { Modal, Table, Button, Space, message, Checkbox, Input, Tag } from 'antd';
import { SearchOutlined, CheckSquareOutlined, BorderOutlined } from '@ant-design/icons';
import { providerAPI } from '../services/api';

export default function FetchModelsModal({ visible, provider, existingModelIds = [], onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [models, setModels] = useState([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [searchText, setSearchText] = useState('');

  // 加载远程模型列表
  useEffect(() => {
    if (visible && provider) {
      loadRemoteModels();
    }
  }, [visible, provider]);

  const loadRemoteModels = async () => {
    setLoading(true);
    try {
      const { data } = await providerAPI.getRemoteModels(provider.id);
      // 标记已存在的模型
      const modelsWithStatus = data.models.map(m => ({
        ...m,
        exists: existingModelIds.includes(m.id),
        display_name: m.id // 默认显示名称为模型ID
      }));
      setModels(modelsWithStatus);
      setSelectedRowKeys([]);
    } catch (error) {
      message.error(error.response?.data?.detail || '获取模型列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 过滤后的模型列表
  const filteredModels = models.filter(m =>
    m.id.toLowerCase().includes(searchText.toLowerCase()) ||
    (m.owned_by && m.owned_by.toLowerCase().includes(searchText.toLowerCase()))
  );

  // 可选的模型（排除已存在的）
  const selectableModels = filteredModels.filter(m => !m.exists);

  // 全选
  const handleSelectAll = () => {
    setSelectedRowKeys(selectableModels.map(m => m.id));
  };

  // 取消全选
  const handleDeselectAll = () => {
    setSelectedRowKeys([]);
  };

  // 批量添加
  const handleSubmit = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要添加的模型');
      return;
    }

    setSubmitting(true);
    try {
      const modelsToAdd = selectedRowKeys.map(id => {
        const model = models.find(m => m.id === id);
        return {
          model_id: id,
          display_name: model?.display_name || id,
          temperature: 0.7,
          max_tokens: 4096
        };
      });

      const { data } = await providerAPI.batchCreateModels(provider.id, modelsToAdd);
      message.success(data.message);
      onSuccess?.();
      onClose();
    } catch (error) {
      message.error(error.response?.data?.detail || '添加失败');
    } finally {
      setSubmitting(false);
    }
  };

  const columns = [
    {
      title: '模型ID',
      dataIndex: 'id',
      key: 'id',
      render: (text, record) => (
        <Space>
          <span style={{ fontFamily: 'monospace' }}>{text}</span>
          {record.exists && <Tag color="orange">已添加</Tag>}
        </Space>
      )
    },
    {
      title: '所有者',
      dataIndex: 'owned_by',
      key: 'owned_by',
      width: 150,
      render: text => text || '-'
    },
    {
      title: '显示名称',
      dataIndex: 'display_name',
      key: 'display_name',
      width: 200,
      render: (text, record, index) => (
        <Input
          size="small"
          value={text}
          disabled={record.exists}
          onChange={e => {
            const newModels = [...models];
            const modelIndex = models.findIndex(m => m.id === record.id);
            if (modelIndex !== -1) {
              newModels[modelIndex] = { ...newModels[modelIndex], display_name: e.target.value };
              setModels(newModels);
            }
          }}
          placeholder="显示名称"
        />
      )
    }
  ];

  const rowSelection = {
    selectedRowKeys,
    onChange: setSelectedRowKeys,
    getCheckboxProps: record => ({
      disabled: record.exists
    })
  };

  return (
    <Modal
      title={`获取模型 - ${provider?.name || ''}`}
      open={visible}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="cancel" onClick={onClose}>取消</Button>,
        <Button
          key="submit"
          type="primary"
          loading={submitting}
          disabled={selectedRowKeys.length === 0}
          onClick={handleSubmit}
        >
          添加选中 ({selectedRowKeys.length})
        </Button>
      ]}
    >
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Space>
          <Input
            placeholder="搜索模型..."
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            style={{ width: 200 }}
            allowClear
          />
          <span style={{ color: '#666' }}>
            共 {models.length} 个模型，已添加 {models.filter(m => m.exists).length} 个
          </span>
        </Space>
        <Space>
          <Button
            icon={<CheckSquareOutlined />}
            onClick={handleSelectAll}
            disabled={selectableModels.length === 0}
          >
            全选
          </Button>
          <Button
            icon={<BorderOutlined />}
            onClick={handleDeselectAll}
            disabled={selectedRowKeys.length === 0}
          >
            取消全选
          </Button>
        </Space>
      </Space>

      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={filteredModels}
        rowKey="id"
        loading={loading}
        size="small"
        scroll={{ y: 400 }}
        pagination={false}
      />
    </Modal>
  );
}
