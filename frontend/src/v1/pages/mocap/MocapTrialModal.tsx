import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Table, Button } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import MocapS3Cursor, { LargeZipBinaryObject } from '../../state/MocapS3Cursor';
import NimbleStandaloneReact from 'nimble-visualizer/dist/NimbleStandaloneReact';
import Select, { components, MultiValueGenericProps, ControlProps, MultiValue, Props } from 'react-select';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    ChartDataset,
    ChartOptions
} from 'chart.js';
import { Line } from 'react-chartjs-2';

type MocapTrialModalProps = {
    cursor: MocapS3Cursor;
};

type ProcessingResultsJSON = {
    autoAvgMax: number;
    autoAvgRMSE: number;
    linearResidual?: number;
    angularResidual?: number;
    goldAvgMax: number;
    goldAvgRMSE: number;
};

type MocapTrialEntry = {
    key: string;
    lastModified: Date;
    size: number;
};

const globalMouseoverIndex = [0];
const globalCurrentFrame = [0];

const chartJSPlugin = {
    id: 'verticalLine',
    afterDraw: (chart: any) => {
        if (chart.scales == null || chart.ctx == null || chart.scales.x == null) return;

        let yAxis: any = null;
        for (const [key, value] of Object.entries(chart.scales)) {
            if (key !== 'x') {
                yAxis = value;
            }
        }

        let ctx = chart.ctx;

        if (chart.tooltip?._active?.length) {
            globalMouseoverIndex[0] = chart.tooltip._active[0].index;

            // Draw the mouseover line
            const mouseoverX = chart.scales.x.getPixelForValue(globalMouseoverIndex[0]);
            ctx.save();
            ctx.beginPath();
            ctx.moveTo(mouseoverX, yAxis.top);
            ctx.lineTo(mouseoverX, yAxis.bottom);
            ctx.lineWidth = 1;
            ctx.strokeStyle = '#aaa';
            ctx.stroke();
            ctx.restore();
        }

        // Draw the current time line
        const currentFrameX = chart.scales.x.getPixelForValue(globalCurrentFrame[0]);
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(currentFrameX, yAxis.top);
        ctx.lineTo(currentFrameX, yAxis.bottom);
        ctx.lineWidth = 1;
        ctx.strokeStyle = '#ff0000';
        ctx.stroke();
        ctx.restore();
    }
};

ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    chartJSPlugin
);

const MocapTrialModal = observer((props: MocapTrialModalProps) => {
    const location = useLocation();
    const navigate = useNavigate();
    const standalone = useRef(null as null | any);
    const [resultsJson, setResultsJson] = useState({} as ProcessingResultsJSON);
    const [plotCSV, setPlotCSV] = useState([] as Map<string, number | boolean>[]);
    const [plotTags, setPlotTags] = useState([] as string[]);
    const [frame, setFrame] = useState(0);
    const chartRef = useRef(null as any);
    const modalRef = useRef(null as any);

    let show = location.search.startsWith("?show-trial=");
    let trialNumber: number = 0;
    let subjectStatus = 'empty'
    let trial: MocapTrialEntry | null = null;
    let visualization: LargeZipBinaryObject | null = null;
    if (show) {
        trialNumber = parseInt(decodeURIComponent(location.search.substring("?show-trial=".length)));
        trial = props.cursor.getTrials()[trialNumber];
        if (trial != null) {
            subjectStatus = props.cursor.getSubjectStatus();
        }
        if (subjectStatus === 'done' && props.cursor.hasTrialVisualization(trial.key)) {
            visualization = props.cursor.getTrialVisualization(trial.key);
        }
    }

    useEffect(() => {
        if (show && trial != null && subjectStatus === 'done') {
            props.cursor.getTrialResultsFileText(trial.key).then((text: string) => {
                setResultsJson(JSON.parse(text));

                // Scroll to the top
                if (modalRef.current != null) {
                    modalRef.current.dialog.scrollTo({ top: 0, behavior: 'smooth' });
                }
            }).catch(() => { });

            props.cursor.getTrialPlotDataCSV(trial.key).then((text: string) => {
                const lines = text.split('\n');
                let headers = lines[0].split(',');
                console.log(headers);
                let dataset: Map<string, number | boolean>[] = [];
                for (let i = 1; i < lines.length; i++) {
                    let values = lines[i].split(',');
                    let valuesMap: Map<string, number | boolean> = new Map();
                    for (let j = 0; j < values.length; j++) {
                        if (values[j].trim() === 'true') {
                            valuesMap.set(headers[j], true);
                        }
                        else if (values[j].trim() === 'false') {
                            valuesMap.set(headers[j], false);
                        }
                        else {
                            let asNumber = Number.parseFloat(values[j]);
                            if (Number.isNaN(asNumber)) {
                                console.warn("Got a non-number type in the trial plot CSV: " + headers[j]);
                                // TODO: handle other datatypes?
                                valuesMap.set(headers[j], 0.0);
                            }
                            else {
                                valuesMap.set(headers[j], asNumber);
                            }
                        }
                    }
                    dataset.push(valuesMap);
                }

                setPlotCSV(dataset);
            }).catch((e) => { });
        }
    }, [trialNumber, show, subjectStatus, trial?.key]); // note: don't depend on props.cursor, because that leads to an infinite loop in rendering

    if (!show || trial == null) {
        return <></>;
    }

    let hideModal = () => {
        if (standalone.current != null) {
            standalone.current.dispose();
            standalone.current = null;
        }
        if (visualization != null) {
            console.log("Disposing of cached visualization");
            visualization.dispose();
        }
        navigate({ search: "" }, { replace: true });
    };


    let body = null;
    if (subjectStatus === 'empty') {

    }
    else if (subjectStatus === 'could-process') {
        if (props.cursor.canEdit()) {
            body = (
                <div className="MocapView">
                    <h2>Status: Ready to process</h2>
                </div>
            );
        }
        else {
            body = (
                <div className="MocapView">
                    <h2>Status: Waiting for owner to process</h2>
                </div>
            );
        }
    }
    else if (subjectStatus === 'waiting') {
        body = (
            <div className="MocapView">
                <h2>Waiting to be assigned a processing server...</h2>
                <p>
                    We have a number of servers that process uploaded tasks one at a
                    time. It shouldn't take long to get assigned a server, but when we
                    get lots of uploads at once, the servers may be busy for a while.
                </p>
            </div>
        );
    }
    else if (subjectStatus === 'processing') {
        body = (
            <div className="MocapView">
                <h2>Status: Processing</h2>
            </div>
        );
    }
    else if (subjectStatus === 'error') {
        body = (
            <div className="MocapView">
                <h2>Processing Server Encountered Error</h2>
            </div>
        );
    }
    else if (subjectStatus === 'done') {
        let percentImprovementRMSE = ((resultsJson.goldAvgRMSE - resultsJson.autoAvgRMSE) / resultsJson.goldAvgRMSE) * 100;
        let percentImprovementMax = ((resultsJson.goldAvgMax - resultsJson.autoAvgMax) / resultsJson.goldAvgMax) * 100;
        let linearResidualText = "N/A";
        let angularResidualText = "N/A";
        if (resultsJson.linearResidual) {
            if (resultsJson.linearResidual >= 100 || resultsJson.linearResidual < 0.1) {
                linearResidualText = (resultsJson.linearResidual).toExponential(2) + "N";
            }
            else {
                linearResidualText = (resultsJson.linearResidual).toFixed(2) + "N";
            }
        }
        if (resultsJson.angularResidual) {
            if (resultsJson.angularResidual >= 100 || resultsJson.angularResidual < 0.1) {
                angularResidualText = (resultsJson.angularResidual).toExponential(2) + "Nm";
            }
            else {
                angularResidualText = (resultsJson.angularResidual).toFixed(2) + "Nm";
            }
        }

        let plot = null;
        if (plotCSV.length > 0) {

            /////////////////////////////////////////////////////////////////
            // Set up the selector so we can toggle data series in and out
            /////////////////////////////////////////////////////////////////

            const customStyles = {
                control: (styles: any) => ({ ...styles, backgroundColor: 'white', border: '1px solid rgb(222, 226, 230)' }),
            };
            let tagOptions: { value: string, label: string }[] = [];
            if (plotCSV.length > 0) {
                plotCSV[0].forEach((v, key) => {
                    if (key !== 'time') {
                        tagOptions.push({ value: key, label: key });
                    }
                });
            }
            let selectedOptions = plotTags.map(key => {
                return {
                    value: key,
                    label: key
                }
            });
            const select =
                <Select
                    isMulti
                    isSearchable
                    styles={customStyles}
                    value={selectedOptions}
                    onChange={(newOptions) => {
                        setPlotTags(newOptions.map(o => o.value));
                    }}
                    options={tagOptions}
                    noOptionsMessage={() => {
                        return "No columns of data available match your search.";
                    }}
                />;

            /////////////////////////////////////////////////////////////////
            // Based on the selected series, build a dataset object
            /////////////////////////////////////////////////////////////////

            let labels = [];
            for (let i = 0; i < plotCSV.length; i++) {
                labels.push(plotCSV[i].get('time'));
            }

            let colors = [
                '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC'
            ];

            let scales: any = {};

            for (let j = 0; j < plotTags.length; j++) {
                let label = plotTags[j];
                if (label.indexOf("tau") !== -1) {
                    if (!scales.hasOwnProperty("Nm")) {
                        scales['Nm'] = {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            ticks: {
                                beginAtZero: true,
                                callback: function (value: any, index: any, values: any) {
                                    return value + ' Nm';
                                }
                            }
                        };
                    }
                }
                else if (label.indexOf("force") !== -1) {
                    if (!scales.hasOwnProperty("N")) {
                        scales['N'] = {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            ticks: {
                                beginAtZero: true,
                                callback: function (value: any, index: any, values: any) {
                                    return value + ' N';
                                }
                            }
                        };
                    }
                }
                else if (label.indexOf("pos") !== -1) {
                    if (!scales.hasOwnProperty("units")) {
                        scales['units'] = {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            ticks: {
                                beginAtZero: true,
                                callback: function (value: any, index: any, values: any) {
                                    return value + ' units';
                                }
                            }
                        };
                    }
                }
                else if (label.indexOf("vel") !== -1) {
                    if (!scales.hasOwnProperty("units/s")) {
                        scales['units/s'] = {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            ticks: {
                                beginAtZero: true,
                                callback: function (value: any, index: any, values: any) {
                                    return value + ' units/s';
                                }
                            }
                        };
                    }
                }
                else if (label.indexOf("acc") !== -1) {
                    if (!scales.hasOwnProperty("units/s^2")) {
                        scales['units/s^2'] = {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            ticks: {
                                beginAtZero: true,
                                callback: function (value: any, index: any, values: any) {
                                    return value + ' units/s^2';
                                }
                            }
                        };
                    }
                } else {
                    if (!scales.hasOwnProperty("")) {
                        scales[""] = {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            ticks: {
                                beginAtZero: true,
                                callback: function (value: any, index: any, values: any) {
                                    return value + ' ""';
                                }
                            }
                        };
                    }
                }
            }

            let datasets: ChartDataset[] = [];
            for (let j = 0; j < plotTags.length; j++) {
                let label = plotTags[j];
                let data: any[] = [];
                for (let i = 0; i < plotCSV.length; i++) {
                    if (plotCSV[i].get('missing_grf_data') && (label.indexOf('tau') !== -1 || label.indexOf('force') !== -1 || label.indexOf('moment') !== -1)) {
                        data.push(null);
                    }
                    else {
                        data.push(plotCSV[i].get(label) as number);
                    }
                }
                let yAxisID = "";
                if (label.indexOf("tau") !== -1) {
                    yAxisID = "Nm";
                }
                else if (label.indexOf("force") !== -1) {
                    yAxisID = "N";
                }
                else if (label.indexOf("pos") !== -1) {
                    yAxisID = "units";
                }
                else if (label.indexOf("vel") !== -1) {
                    yAxisID = "units/s";
                }
                else if (label.indexOf("acc") !== -1) {
                    yAxisID = "units/s^2";
                }
                datasets.push({
                    label: label,
                    data,
                    borderColor: colors[j % colors.length],
                    backgroundColor: colors[j % colors.length],
                    borderWidth: 3,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    spanGaps: false,
                    yAxisID: yAxisID
                });
            }

            // Get all the data for each axis in a single array
            const axisDataMap: Map<string, number[]> = new Map();
            for (let i = 0; i < datasets.length; i++) {
                const yAxisID: string = (datasets[i] as any).yAxisID;
                const data: number[] = datasets[i].data as any as number[];
                axisDataMap.set(yAxisID, (axisDataMap.get(yAxisID) ?? []).concat(data));
            }

            // Compute the min and max percentages of range across all the datasets
            let maxValueAsPercentageOverall = 0.0;
            let minValueAsPercentageOverall = 0.0;
            const axisDataRanges: Map<string, number> = new Map();
            axisDataMap.forEach((data: number[], yAxisID: string) => {
                let minValue = data.reduce((a, b) => {
                    return Math.min(a, b);
                }, 0);
                let maxValue = data.reduce((a, b) => {
                    return Math.max(a, b);
                }, 0);
                let range = maxValue - minValue;

                // Reset the range to be at a nice clean power of ten number
                let rangeFloorPowerOfTen = Math.pow(10, Math.floor(Math.log10(range)));
                minValue = Math.min(0, rangeFloorPowerOfTen * Math.floor(minValue / rangeFloorPowerOfTen));
                maxValue = Math.max(0, rangeFloorPowerOfTen * Math.ceil(maxValue / rangeFloorPowerOfTen));
                range = maxValue - minValue;

                const maxValueAsPercentage = maxValue / range;
                if (maxValueAsPercentage > maxValueAsPercentageOverall) {
                    maxValueAsPercentageOverall = maxValueAsPercentage;
                }
                const minValueAsPercentage = minValue / range;
                if (minValueAsPercentage < minValueAsPercentageOverall) {
                    minValueAsPercentageOverall = minValueAsPercentage;
                }
                axisDataRanges.set(yAxisID, range);
            });

            // Set the ticks on each axis so that the zero points are at the same percentage on all the datasets
            axisDataMap.forEach((data: number[], yAxisID: string) => {
                scales[yAxisID].min = minValueAsPercentageOverall * (axisDataRanges.get(yAxisID) ?? 0.0);
                scales[yAxisID].max = maxValueAsPercentageOverall * (axisDataRanges.get(yAxisID) ?? 0.0);
            });
            console.log(scales);

            let options: any = {
                scales,
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function (context: any) {
                                let label = context.dataset.label || '';

                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y;
                                }
                                if (label.indexOf("tau") !== -1) {
                                    label += " Nm";
                                }
                                else if (label.indexOf("force") !== -1) {
                                    label += " N";
                                }
                                else if (label.indexOf("pos") !== -1) {
                                    label += " units";
                                }
                                else if (label.indexOf("vel") !== -1) {
                                    label += " units/s";
                                }
                                else if (label.indexOf("acc") !== -1) {
                                    label += " units/s^2";
                                }
                                return label;
                            }
                        }
                    }
                }
            };

            let data = {
                labels, datasets
            };

            let downloadButton = null;
            if (trial != null) {
                const trialName = trial.key;
                downloadButton = (
                    <Button onClick={() => props.cursor.downloadTrialResultsCSV(trialName)}>
                        <i className="mdi mdi-download me-2 vertical-middle"></i>
                        Download Raw Data CSV
                    </Button>
                );
            }

            plot = <div>
                <p>
                    Analyze the results:
                </p>
                {select}
                <Line data={data as any} options={options} ref={(r) => {
                    chartRef.current = r;
                }} onMouseDownCapture={(e) => {
                    const onMouseEvent = (e: any) => {
                        e.preventDefault();
                        globalCurrentFrame[0] = globalMouseoverIndex[0];
                        setFrame(globalCurrentFrame[0]);
                    };
                    onMouseEvent(e);

                    window.addEventListener('mousemove', onMouseEvent);

                    const onMouseUp = () => {
                        window.removeEventListener('mousemove', onMouseEvent);
                        window.removeEventListener('mouseup', onMouseUp);
                    }
                    window.addEventListener('mouseup', onMouseUp);
                }} />
                <div className="mt-2">
                    {downloadButton}
                </div>
            </div>;
        }

        /*
        body = (
            <div className="MocapView">
                <NimbleStandaloneReact
                    style={{ height: '400px' }}
                    loading={visualization?.loading ?? true}
                    loadingProgress={visualization?.loadingProgress ?? 0.0}
                    recording={visualization?.object ?? null}
                    frame={frame}
                    onFrameChange={(newFrame) => {
                        globalCurrentFrame[0] = newFrame;
                        if (chartRef.current != null) {
                            chartRef.current.update();
                        }
                        // setFrame(newFrame);
                    }}
                />
                <div>
                    <Table>
                        <thead>
                            <tr>
                                <td></td>
                                <td>Avg. Marker-error RMSE</td>
                                <td>Avg. Marker-error Max</td>
                                <td>Avg. Linear Residual</td>
                                <td>Avg. Angular Residual</td>
                            </tr>
                        </thead>
                        <tbody>
                            {(() => {
                                if (!isNaN(resultsJson.goldAvgRMSE)) {
                                    return (
                                        <tr>
                                            <td>Hand-scaling Performance:</td>
                                            <td>{(resultsJson.goldAvgRMSE * 100 ?? 0.0).toFixed(2)} cm</td>
                                            <td>{(resultsJson.goldAvgMax * 100 ?? 0.0).toFixed(2)} cm</td>
                                        </tr>
                                    );
                                }
                            })()}
                            <tr>
                                <td>Auto-scaling Performance:</td>
                                <td>{(resultsJson.autoAvgRMSE * 100 ?? 0.0).toFixed(2)} cm {
                                    isNaN(percentImprovementRMSE) ? null : <b>({percentImprovementRMSE.toFixed(1)}% error {percentImprovementRMSE > 0 ? 'reduction' : 'increase'})</b>
                                }</td>
                                <td>{(resultsJson.autoAvgMax * 100 ?? 0.0).toFixed(2)} cm {
                                    isNaN(percentImprovementMax) ? null : <b>({percentImprovementMax.toFixed(1)}% error {percentImprovementMax > 0 ? 'reduction' : 'increase'})</b>
                                }</td>
                                <td>{linearResidualText}</td>
                                <td>{angularResidualText}</td>
                            </tr>
                        </tbody>
                    </Table>
                </div>
                {plot}
            </div>
        );
        */
    }

    return (
        <Modal size="xl" show={show} onHide={hideModal} ref={modalRef}>
            <Modal.Header closeButton>
                <Modal.Title>
                    <i className="mdi mdi-run me-1"></i> Trial: {trial.key}
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>{body}</Modal.Body>
        </Modal>
    );
});

export default MocapTrialModal;
