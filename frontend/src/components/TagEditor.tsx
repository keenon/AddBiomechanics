import React, { useState, useRef } from "react";
import Select, { components, MultiValueGenericProps, ControlProps, MultiValue } from 'react-select';
import './TagEditor.scss';

type Option = {
  value: string,
  label: string,
  addedNumberUnits?: string,
  min?: number,
  max?: number,
  integer?: boolean
}

const subjectOptions: Option[] = [
  { value: 'age', label: 'Age', addedNumberUnits: 'years', min: 16, max: 90, integer: true },
  { value: 'healthy', label: 'Healthy Subject' },
  { value: 'parkinsons', label: 'Parkinsons' },
  { value: 'freezing_of_gait', label: 'Freezing of Gait' },
  { value: 'muscular_distrophy', label: 'Muscular Distrophy' },
];

const trialOptions: Option[] = [
  { value: 'exo_powered', label: 'Exo - Powered' },
  { value: 'exo_unpowered', label: 'Exo - Unpowered' },
  { value: 'exo_passive', label: 'Exo - Passive' },
  { value: 'movement_speed', label: 'Movement Speed', addedNumberUnits: 'm/s' },
  { value: 'treadmill_angle', label: 'Treadmill Angle', addedNumberUnits: 'deg' },
  { value: 'running', label: 'Running' },
  { value: 'walking', label: 'Walking' },
  { value: 'sit_to_stand', label: 'Sit to Stand' },
  { value: 'jump', label: 'Jump' },
  { value: 'calibration', label: 'Calibration' },
  { value: 'dance', label: 'Dance' },
];

const MultiValueLabel = (props: MultiValueGenericProps<Option>) => {
  let numberValues = (props.selectProps as any).numberValues;
  const [value, setValue] = useState(props.data.value in numberValues ? numberValues[props.data.value] : 0.0);
  const inputRef = useRef(null as any as HTMLInputElement);

  let numberInput = null;
  if (props.data.addedNumberUnits != null) {
    numberInput = <span>
      :<input className="TagEditor__number_input" type="number" ref={inputRef} onKeyDown={(e) => { e.stopPropagation(); }} onKeyPress={(e) => {
        e.stopPropagation();
        if (e.key === "Enter" && inputRef.current != null) {
          inputRef.current.blur();
        }
      }} value={value} onChange={(e) => {
        let rawValue = parseFloat(e.target.value);
        setValue(rawValue);
      }} onBlur={() => {
        const onChangeOption = (props.selectProps as any).onChangeOption;
        let rawValue = value;
        if (props.data.integer) {
          rawValue = Math.round(rawValue);
        }
        if (props.data.min != null && rawValue < props.data.min) {
          rawValue = props.data.min;
        }
        if (props.data.max != null && rawValue > props.data.max) {
          rawValue = props.data.max;
        }
        setValue(rawValue);
        onChangeOption(props.data, value);
      }} />
      {props.data.addedNumberUnits}
    </span>;
  }

  return (
    <div className="TagEditor__tag">
      {props.children}
      {numberInput}
    </div>
  )
}

type TagEditorProps = {
  isSubject: boolean,
  tags: string[],
  tagValues: { [key: string]: number },
  onTagsChanged: (tags: string[]) => void,
  onTagValuesChanged: (tagValues: { [key: string]: number }) => void,
  onFocus: () => void,
  onBlur: () => void,
};

const TagEditor = (props: TagEditorProps) => {
  const onChange = (newOptions: MultiValue<Option>) => {
    props.onTagsChanged(newOptions.map(o => o.value));
  }

  const customStyles = {
    control: (styles: any) => ({ ...styles, backgroundColor: 'white', border: '1px solid rgb(222, 226, 230)' }),
  }

  const onChangeOption = (option: Option, newValue: number) => {
    let newValues = { ...props.tagValues };
    newValues[option.value] = newValue;
    props.onTagValuesChanged(newValues);
  }

  const optionList = props.isSubject ? subjectOptions : trialOptions;

  const selectedOptions = props.tags.flatMap(key => {
    return optionList.filter(o => o.value === key);
  });

  return (
    <div className="TagEditor">
      <Select
        isMulti
        isSearchable
        styles={customStyles}
        components={{ MultiValueLabel }}
        value={selectedOptions}
        onChange={onChange}
        onFocus={props.onFocus}
        onBlur={props.onBlur}
        // @ts-ignore
        onChangeOption={onChangeOption}
        // @ts-ignore
        numberValues={props.tagValues}
        options={optionList}
        noOptionsMessage={() => {
          return "No tags match your search. We use structured tags, instead of free form text notes, to avoid accidentally hosting Personally Identifiable Information (PII) on the platform. If you don't find the tags you need, feel free to tweet at @KeenonWerling and suggest new tags!";
        }}
      />
    </div>
  );
};

export default TagEditor;
