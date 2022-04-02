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

class Lieu(dict):
  def __init__(self, lieu, semester_start):
    self.semester_start = semester_start
    super().__init__(lieu)
    self.holiday_dates = self.get_holiday_dates()
    self.course_list = self.get_course_list()
  def get_date(self, week, day):
    return self.semester_start + datetime.timedelta(weeks=week-1) + datetime.timedelta(days=day-1)
  def get_holiday_dates(self):
    dates = []
    holidays = self['holidays']
    for holiday in holidays:
      week = holiday['week']
      days = holiday['days']
      dates += [self.get_date(week, day) for day in days]
    return dates
  def get_course_list(self):
    return [[self.get_date(course[tag]['week'], course[tag]['day']) for tag in ['from', 'to']] for course in self['courses']]

class Semester(dict):
  def get_date(self, week, day):
    return self['start'] + datetime.timedelta(weeks=week-1) + datetime.timedelta(days=day-1)
  def export_holiday_event(self):
    if 'lieux' not in self.keys():
      return
    lieux = self['lieux']
    for lieu in lieux:
      lieu = Lieu(lieu, self['start'])
      lieu_name = lieu['name']
      holidays = lieu['holidays']
      for index, holiday in enumerate(holidays):
        week = holiday['week']
        days = holiday['days']
        first_day = days[0]
        last_day = days[-1] + 1
        first_date = self.get_date(week, first_day)
        last_date = self.get_date(week, last_day)
        write_to_file('''BEGIN:VEVENT
UID:%s:%s#%s
DTSTAMP:%s
SUMMARY:%s
DTSTART;TZID=Asia/Shanghai;VALUE=DATE:%s
DTEND;TZID=Asia/Shanghai;VALUE=DATE:%s
END:VEVENT
''' % (self['name'], lieu_name, index, get_current_timestamp(), lieu_name + '假期', format_date(first_date), format_date(last_date))
        )
      for from_date, to_date in lieu.course_list:
        write_to_file('''BEGIN:VEVENT
UID:%s:%s@%s
DTSTAMP:%s
SUMMARY:%s
DTSTART;TZID=Asia/Shanghai;VALUE=DATE:%s
DTEND;TZID=Asia/Shanghai;VALUE=DATE:%s
END:VEVENT
''' % (self['name'], lieu_name, format_date(to_date), get_current_timestamp(), '{}调休 ({})'.format(lieu_name, from_date.isoformat()), format_date(to_date), format_date(to_date + datetime.timedelta(days=1)))
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
    if 'lieux' in semester.keys():
      semester_lieux = [Lieu(lieu, semester_start) for lieu in semester['lieux']]
    else:
      semester_lieux = [] # TODO: refactor Semester['lieux']
    semester.export_holiday_event()
    for course in semester['courses']:
      course_id = course['id']
      course_name = course['name']
      course_teacher = course['teacher']
      for index, schedule in enumerate(course['schedule']):
        fake_weeks = schedule['weeks']
        first_week = fake_weeks[0]
        last_week = fake_weeks[-1]
        day = schedule['day']
        skip = schedule.get('skip', 1)
        weeks = list(range(first_week, last_week + 1, skip))
        dates = [semester.get_date(week, day) for week in weeks]
        first_date = dates[0]
        last_date = dates[-1]
        period = schedule['periods']
        first_period = period[0]
        second_period = period[-1]
        start_time = datetime.time.fromisoformat(periods[first_period]['start'])
        end_time = datetime.time.fromisoformat(periods[second_period]['end'])
        exdates = []
        rdates = []
        for lieu in semester_lieux:
          temp_holiday_dates = [date for date in dates if date in lieu.holiday_dates]
          exdates += temp_holiday_dates
          exdates += [to_date for _, to_date in lieu.course_list if to_date in dates]
          rdates += [[lieu['name'], to_date, from_date] for from_date, to_date in lieu.course_list if from_date in temp_holiday_dates]
          # rdates += [[lieu['name'], from_date, to_date] for from_date, to_date in lieu.course_list if to_date in dates]

        exdates_text = ','.join(['{}T{}Z'.format(format_date(date), format_time(start_time)) for date in exdates])
        exdate_line = '' if exdates_text == '' else 'EXDATE;TZID=Asia/Shanghai:{}\n'.format(exdates_text)
        # rdates_text = ','.join(['{}T{}Z'.format(format_date(date), format_time(start_time)) for date in rdates])
        # rdate_line = '' if rdates_text == '' else 'RDATE;TZID=Asia/Shanghai:{}\n'.format(rdates_text)
        location = schedule['location']
        description = r'课程代码: {}\n任课教师: {}'.format(course_id, course_teacher)
        write_to_file('''BEGIN:VEVENT
UID:%s:%s#%s
DTSTAMP:%s
LOCATION:%s
SUMMARY:%s
DTSTART;TZID=Asia/Shanghai:%sT%s
DTEND;TZID=Asia/Shanghai:%sT%s
%sRRULE:FREQ=WEEKLY;INTERVAL=%s;UNTIL=%sT240000Z
DESCRIPTION:%s
END:VEVENT
''' % (semester_name, course_name, index, get_current_timestamp(), format_location(location), course_name, first_date.strftime('%Y%m%d'), start_time.strftime('%H%M%S'), first_date.strftime('%Y%m%d'), end_time.strftime('%H%M%S'), exdate_line, skip, last_date.strftime('%Y%m%d'), description))
        for lieu_name, to_date, from_date in rdates:
          write_to_file('''BEGIN:VEVENT
UID:%s:%s@%s
DTSTAMP:%s
LOCATION:%s
SUMMARY:%s
DTSTART;TZID=Asia/Shanghai:%sT%s
DTEND;TZID=Asia/Shanghai:%sT%s
DESCRIPTION:%s
END:VEVENT
''' % (semester_name, course_name, format_date(to_date), get_current_timestamp(), format_location(location), course_name, to_date.strftime('%Y%m%d'), start_time.strftime('%H%M%S'), to_date.strftime('%Y%m%d'), end_time.strftime('%H%M%S'), r'{}调休自 {}\n'.format(lieu_name, from_date.isoformat())+description))
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

def format_time(time):
  return time.strftime('%H%M%S')

if __name__ == '__main__':
  main()
