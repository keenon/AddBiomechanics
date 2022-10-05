import React, { useState, useRef, useEffect } from "react";
import Select, { components, MultiValueGenericProps, ControlProps, MultiValue, Props } from 'react-select';
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
  { value: 'cerebral_palsy', label: 'Cerebral Palsy' },
  { value: 'spina_bifida', label: 'Spina Bifida' },
  { value: 'stroke', label: 'Stroke' },
  { value: 'stroke_left_hemiparesis', label: 'Stroke Left Hemiparesis' },
  { value: 'stroke_right_hemiparesis', label: 'Stroke Right Hemiparesis' },
  { value: 'blind', label: 'Blind' },
  { value: 'visually_impaired', label: 'Visually Impaired' },
  { value: 'trans_femoral_amputation_left', label: 'Trans-femoral Amputation - Left' },
  { value: 'trans_femoral_amputation_right', label: 'Trans-femoral Amputation - Right' },
  { value: 'trans_tibial_amputation_left', label: 'Trans-tibial Amputation - Left' },
  { value: 'trans_tibial_amputation_right', label: 'Trans-tibial Amputation - Right' },
  { value: 'osteoarthritis', label: 'Osteoarthritis' },
  { value: 'knee_osteoarthritis_right', label: 'Knee Osteoarthritis - Right' },
  { value: 'knee_osteoarthritis_left', label: 'Knee Osteoarthritis - Left' },
  { value: 'pregnant', label: 'Pregnant' },
  { value: 'post_partum', label: 'Postpartum' },
];

const trialOptions: Option[] = [
  { value: 'exo_powered', label: 'Exo - Powered' },
  { value: 'exo_unpowered', label: 'Exo - Unpowered' },
  { value: 'exo_passive', label: 'Exo - Passive' },
  { value: 'split_belt', label: 'Split-belt Treadmill' },
  { value: 'out_of_lab', label: 'Out of Lab' },
  { value: 'prosthetic_powered', label: 'Prosthetic - Powered' },
  { value: 'prosthetic_passive', label: 'Prosthetic - Passive' },
  { value: 'stair_climbing', label: 'Stairs - Climbing' },
  { value: 'stair_descending', label: 'Stairs - Descending' },
  { value: 'biking', label: 'Biking' },
  { value: 'loaded_walking', label: 'Loaded Walking', addedNumberUnits: 'kg' },
  { value: 'movement_speed', label: 'Movement Speed', addedNumberUnits: 'm/s' },
  { value: 'treadmill_speed', label: 'Treadmill Speed', addedNumberUnits: 'm/s' },
  { value: 'treadmill_angle', label: 'Treadmill Angle', addedNumberUnits: 'deg' },
  { value: 'running', label: 'Running' },
  { value: 'walking', label: 'Walking' },
  { value: 'blindfolded', label: 'Blindfolded' },
  { value: 'balance_perturbation_impulse', label: 'Balance Perturbation Impulse', addedNumberUnits: 'N*s' },
  { value: 'balance_perturbation_angle', label: 'Balance Perturbation Angle', addedNumberUnits: 'deg' },
  { value: 'sit_to_stand', label: 'Sit to Stand' },
  { value: 'jump', label: 'Jump' },
  { value: 'calibration', label: 'Calibration' },
  { value: 'dance', label: 'Dance' },
  { value: 'rigid_brace_left_ankle', label: 'Brace (Rigid) - Left Ankle' },
  { value: 'rigid_brace_right_ankle', label: 'Brace (Rigid) - Right Ankle' },
  { value: 'rigid_brace_left_knee', label: 'Brace (Rigid) - Left Knee' },
  { value: 'rigid_brace_right_knee', label: 'Brace (Rigid) - Right Knee' },
  { value: 'rigid_brace_left_hip', label: 'Brace (Rigid) - Left Hip' },
  { value: 'rigid_brace_right_hip', label: 'Brace (Rigid) - Right Hip' },
  { value: 'pneumatic_jets_shoes', label: 'Pneumatic Jets (Shoes)' },
  { value: 'arms_crossed', label: 'Arms Crossed' },
];

const MultiValueLabel = (props: MultiValueGenericProps<Option>) => {
  let numberValues = (props.selectProps as any).numberValues;
  let hideNumbers = (props.selectProps as any).hideNumbers;
  const [value, setValue] = useState(props.data.value in numberValues ? numberValues[props.data.value] : 0.0);
  const inputRef = useRef(null as any as HTMLInputElement);

  useEffect(() => {
    setValue(numberValues[props.data.value]);
  }, [numberValues[props.data.value]])

  let numberInput = null;
  if (props.data.addedNumberUnits != null && !hideNumbers) {
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
        if ((props.data.min != null) && rawValue < props.data.min) {
          rawValue = props.data.min;
        }
        if ((props.data.max != null) && rawValue > props.data.max) {
          rawValue = props.data.max;
        }
        setValue(rawValue);
        onChangeOption(props.data, rawValue);
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

const NoOptionsMessage = () => {
  const formURL = "https://docs.google.com/forms/d/e/1FAIpQLScqGhozFWp-33WoO8g9WGda3bf8cm2bvcDtIM1F7jAifwcIlw/viewform?usp=sf_link";

  return <div className="m-2">
    No tags match your search. We use structured tags, instead of free form text notes, to avoid accidentally hosting Personally Identifiable Information (PII) on the platform. If you don't find the tags you need, fill out <a href={formURL} target="_blank">this form</a> (opens in a new tab) to request new tags!
  </div>
}

type TagEditorProps = {
  tagSet: 'subject' | 'trial' | string[],
  tags: string[],
  tagValues: { [key: string]: number },
  onTagsChanged: (tags: string[]) => void,
  onTagValuesChanged: (tagValues: { [key: string]: number }) => void,
  onFocus?: () => void,
  onBlur?: () => void,
  hideNumbers?: boolean
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

  let optionList: Option[] = [];
  if (props.tagSet === 'subject') optionList = subjectOptions;
  else if (props.tagSet === 'trial') optionList = trialOptions;
  else {
    for (let key of props.tagSet) {
      optionList.push({
        value: key,
        label: key
      });
    }
  }

  const selectedOptions = props.tags.flatMap(key => {
    return optionList.filter(o => o.value === key);
  });

  return (
    <div className="TagEditor">
      <Select
        isMulti
        isSearchable
        styles={customStyles}
        components={{ MultiValueLabel, NoOptionsMessage }}
        value={selectedOptions}
        onChange={onChange}
        onFocus={props.onFocus}
        onBlur={props.onBlur}
        // @ts-ignore
        onChangeOption={onChangeOption}
        // @ts-ignore
        numberValues={props.tagValues}
        // @ts-ignore
        hideNumbers={props.hideNumbers}
        options={optionList}
        noOptionsMessage={() => {
          return "No tags match your search. We use structured tags, instead of free form text notes, to avoid accidentally hosting Personally Identifiable Information (PII) on the platform. If you don't find the tags you need, feel free to tweet at @KeenonWerling and suggest new tags!";
        }}
      />
    </div>
  );
};

export default TagEditor;
