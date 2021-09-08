import datetime
import os
import re
import yaml


class Range(list):
  def __new__(cls, start, end):
    return list(range(start, end + 1))
  def __repr__(self):
    return 'Range(%s, %s)'

def range_representer(dumper, data):
  return dumper.represent_scalar('!range', '%s-%s' % data)
def range_constructor(loader, node):
  value = loader.construct_scalar(node)
  start, stop = map(int, value.split('-'))
  return Range(start, stop)

class Time(datetime.time):
  def __new__(cls, time):
    return datetime.time.fromisoformat(time)
  def __repr__(self):
    return 'Time(%s)'

class Semester(dict):
  def get_date(self, week, day):
    return self['start'] + datetime.timedelta(weeks=week-1) + datetime.timedelta(days=day-1)
  def export_holiday_event(self):
    lieux = self['lieux']
    for lieu in lieux:
      lieu_name = lieu['name']
      holidays = lieu['holidays']
      for index, holiday in enumerate(holidays):
        week = holiday['week']
        day = holiday['day']
        first_day = day[0]
        last_day = day[-1] + 1
        first_date = self.get_date(week, first_day)
        last_date = self.get_date(week, last_day)
        write_to_file('''BEGIN:VEVENT
UID:%s:%s@%s
DTSTAMP:%s
SUMMARY:%s
DTSTART;TZID=Asia/Shanghai;VALUE=DATE:%s
DTEND;TZID=Asia/Shanghai;VALUE=DATE:%s
END:VEVENT
''' % (self['name'], lieu_name, index, get_current_timestamp(), lieu_name + '假期', format_date(first_date), format_date(last_date))
)

LOCATION = {
  'H': r'\n上海市杨浦区邯郸路 220 号复旦大学邯郸校区\, 上海\, 上海\, 200433',
  'J': r'\n上海市杨浦区淞沪路 2005 号复旦大学江湾校区\, 上海\, 上海\, 200438'
}

def format_location(text:str):
  return r'{}{}'.format(text, LOCATION.get(text[0], ''))

def main():
  yaml.add_representer(Range, range_representer)
  yaml.add_constructor('!range', range_constructor)
  range_pattern = re.compile('^\d+-\d+$')
  yaml.add_implicit_resolver('!range', range_pattern)

  with open('graduate.yaml', encoding='UTF-8') as f:
    contents = yaml.load(f.read(), Loader=yaml.FullLoader)
  periods = contents['periods']
  write_to_file('''BEGIN:VCALENDAR
VERSION:2.0
X-WR-CARNAME:%s
PRODID:Python
X-WR-TIMEZONE;VALUE=TEXT:Asia/Shanghai
CALSCALE:GREGORIAN
METHOD:PUBLISH
''' % contents['name'], 'w')
  for semester in contents['semesters']:
    semester = Semester(semester)
    semester_name = semester['name']
    semester_start = semester['start']
    semester_lieux = semester['lieux']
    semester.export_holiday_event()
    for course in semester['courses']:
      course_id = course['id']
      course_name = course['name']
      course_teacher = course['teacher']
      for index, schedule in enumerate(course['schedule']):
        week = schedule['week']
        first_week = week[0]
        last_week = week[-1]
        day = schedule['day']
        first_date = semester.get_date(first_week, day)
        last_date = semester.get_date(last_week, day)
        skip = schedule.get('skip', 1)
        period = schedule['period']
        first_period = period[0]
        second_period = period[-1]
        start_time = datetime.time.fromisoformat(periods[first_period]['start'])
        end_time = datetime.time.fromisoformat(periods[second_period]['end'])
        location = schedule['location']
        description = r'课程代码: {}\n任课教师: {}'.format(course_id, course_teacher)
        write_to_file('''BEGIN:VEVENT
UID:%s:%s#%s
DTSTAMP:%s
LOCATION:%s
SUMMARY:%s
DTSTART;TZID=Asia/Shanghai:%sT%s
DTEND;TZID=Asia/Shanghai:%sT%s
RRULE:FREQ=WEEKLY;INTERVAL=%s;UNTIL=%sT240000Z
DESCRIPTION:%s
END:VEVENT
''' % (semester_name, course_name, index, get_current_timestamp(), format_location(location), course_name, first_date.strftime('%Y%m%d'), start_time.strftime('%H%M%S'), first_date.strftime('%Y%m%d'), end_time.strftime('%H%M%S'), skip, last_date.strftime('%Y%m%d'), description))
  write_to_file('END:VCALENDAR')

def write_to_file(text, parameter='a'):
  filename = 'output/graduate.ics'
  os.makedirs(os.path.dirname(filename), exist_ok=True)
  with open(filename, parameter, encoding='UTF-8') as f:
    f.write(text)

def get_current_timestamp():
  return datetime.datetime.now().strftime('%Y%m%dT%H%M%S')

def format_date(date):
  return date.strftime('%Y%m%d')

if __name__ == '__main__':
  main()
