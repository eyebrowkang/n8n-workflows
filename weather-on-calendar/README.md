# Weather On Calendar

在日历上显示天气

## 必备条件

- 一个[OpenWeather](https://openweathermap.org/)的凭证
- 一个n8n账号
- 一个CalDAV账号

## 使用步骤

1. 在n8n添加OpenWeather凭证
2. 导入本仓库的json文件到工作流
3. 修改HTTP Request的URL中的经纬度以及OpenWeatherMap API
4. 修改Weather to CalDAV中的代码内的配置区域部分
5. 手动触发测试

## 补充说明

- 我设置的Schedule是半小时一次，OpenWeather有每天1000次的免费额度，因此一定是够用的，有需要可以自行调整
