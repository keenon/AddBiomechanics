import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { Table, Button } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import { action } from 'mobx';
import NimbleStandaloneReact from 'nimble-visualizer/dist/NimbleStandaloneReact';
import Select from 'react-select';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    ChartDataset
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import UserHomeDirectory, { FolderReviewStatus, TrialSegmentContents } from "../../model/UserHomeDirectory";
import Session from "../../model/Session";
import LiveJsonFile from "../../model/LiveJsonFile";
import LiveFile from "../../model/LiveFile";

type ProcessingResultsJSON = {
    autoAvgMax: number;
    autoAvgRMSE: number;
    linearResidual?: number;
    angularResidual?: number;
    goldAvgMax: number;
    goldAvgRMSE: number;
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

type TrialSegmentViewProps = {
    home: UserHomeDirectory;
    path: string;
    currentLocationUserId: string;
    readonly: boolean;
};

const TrialSegmentView = observer((props: TrialSegmentViewProps) => {
    const location = useLocation();
    const navigate = useNavigate();
    const standalone = useRef(null as null | any);
    const [playing, setPlaying] = useState(false);
    const [previewUrl, setPreviewUrl] = useState("");
    const [resultsJson, setResultsJson] = useState({} as ProcessingResultsJSON);
    const [plotCSV, setPlotCSV] = useState([] as Map<string, number | boolean>[]);
    const [plotTags, setPlotTags] = useState([] as string[]);
    const [frame, setFrame] = useState(0);
    const [draggingFrameWand, setDraggingFrameWand] = useState(false);
    const navigateToNext = useRef((() => { }) as any);
    const chartRef = useRef(null as any);
    const modalRef = useRef(null as any);

    const home = props.home;
    const path = props.path;
    const segmentContents: TrialSegmentContents = home.getTrialSegmentContents(path);
    const dir = home.dir;

    // We cache the review state, so we don't slow things down when huge numbers of segments are being reviewed
    const [reviewState, setReviewState] = useState({
        loading: true,
        path: path,
        segmentsNeedReview: [],
        segmentsReviewed: []
    } as FolderReviewStatus);
    useEffect(() => {
        setReviewState(home.getReviewStatus(path));
    }, []);

    const [csvMissingGrfArray, setCsvMissingGrfArray] = useState([] as boolean[]);

    const missingGrfArray: boolean[] = segmentContents.reviewJson.getAttribute('missing_grf_data', csvMissingGrfArray);

    // useEffect(() => {
    //     const enterListerener = (e: KeyboardEvent) => {
    //         e.preventDefault();
    //         e.stopPropagation();

    //         if (e.key === 'Enter') {
    //             if (navigateToNext.current != null) {
    //                 navigateToNext.current();
    //             }
    //         }
    //     };
    //     window.addEventListener('keypress', enterListerener);
    //     return () => {
    //         window.removeEventListener('keypress', enterListerener);
    //     };
    // });

    useEffect(() => {
        dir.getSignedURL(segmentContents.previewPath, 3600).then((url: string) => {
            setPreviewUrl(url);
        }).catch((e) => {
            console.error(e);
        });

        // Load the results JSON
        dir.downloadText(segmentContents.resultsJsonPath).then((text: string) => {
            setResultsJson(JSON.parse(text));

            // Scroll to the top
            if (modalRef.current != null) {
                modalRef.current.dialog.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }).catch(() => { });

        // Load the results CSV, for plotting quantities
        dir.downloadText(segmentContents.dataPath).then((text: string) => {
            const lines = text.split('\n');
            let headers = lines[0].split(',');
            let dataset: Map<string, number | boolean>[] = [];
            let csvMissingGrfArray: boolean[] = [];
            for (let i = 1; i < lines.length; i++) {
                let values = lines[i].split(',');
                let valuesMap: Map<string, number | boolean> = new Map();
                for (let j = 0; j < values.length; j++) {
                    if (values[j].toLocaleLowerCase().trim() === 'true') {
                        valuesMap.set(headers[j], true);
                    }
                    else if (values[j].toLocaleLowerCase().trim() === 'false') {
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
                    if (headers[j] === 'missing_grf_data') {
                        csvMissingGrfArray.push(valuesMap.get(headers[j]) as boolean);
                    }
                }
                dataset.push(valuesMap);
            }

            if (csvMissingGrfArray.length === 0) {
                csvMissingGrfArray = new Array(dataset.length).fill(true);
            }

            console.log(csvMissingGrfArray);
            setCsvMissingGrfArray(csvMissingGrfArray);
            setPlotCSV(dataset);
        }).catch((e) => { });
    }, [path]);

    let body = null;
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

    ////////////////////////////////////////////////////////////////////////////////////
    // Set up the plot
    ////////////////////////////////////////////////////////////////////////////////////

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
                if (key !== 'timestamp') {
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
                placeholder="Select data series to plot"
                styles={customStyles}
                value={selectedOptions}
                onChange={(newOptions) => {
                    setPlotTags(newOptions.map(o => o.value));
                }}
                options={tagOptions}
                noOptionsMessage={() => {
                    return "No columns of data available match your search.";
                }}
                onKeyDown={(e) => {
                    console.log("Key down: ", e.key);
                    if (e.key === ' ') {
                        console.log("Spacebar pressed");
                        e.preventDefault();
                        e.stopPropagation();
                        setPlaying(!playing);
                    }
                    return false;
                }}
            />;

        /////////////////////////////////////////////////////////////////
        // Based on the selected series, build a dataset object
        /////////////////////////////////////////////////////////////////

        let labels = [];
        for (let i = 0; i < plotCSV.length; i++) {
            labels.push(plotCSV[i].get('timestamp'));
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
                // data.push(plotCSV[i].get(label) as number);
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

        let options: any = {
            responsive: true,
            maintainAspectRatio: false,
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
        if (dir != null) {
            downloadButton = (
                <Button onClick={() => dir.downloadFile(segmentContents.dataPath)}>
                    <i className="mdi mdi-download me-2 vertical-middle"></i>
                    Download Raw Data CSV
                </Button>
            );
        }

        let body = null;
        if (selectedOptions.length === 0) {
            body = <h1>Select Options to Plot ^</h1>
        }
        else {
            body = <Line data={data as any} options={options} ref={(r) => {
                chartRef.current = r;
            }} onMouseDownCapture={(e) => {
                const onMouseEvent = (e: any) => {
                    e.preventDefault();
                    globalCurrentFrame[0] = globalMouseoverIndex[0];
                    setFrame(globalCurrentFrame[0]);
                    setPlaying(false);
                };
                onMouseEvent(e);

                window.addEventListener('mousemove', onMouseEvent);

                const onMouseUp = () => {
                    window.removeEventListener('mousemove', onMouseEvent);
                    window.removeEventListener('mouseup', onMouseUp);
                }
                window.addEventListener('mouseup', onMouseUp);
            }} />
        }

        plot = <>
            <div style={{ height: '50px' }}>
                {select}
            </div>
            <div style={{ height: 'calc(50vh - 50px)' }}>
                {body}
            </div>;
        </>;
    }

    ////////////////////////////////////////////////////////////////////////////////////
    // Set up the 3D Visualizer
    ////////////////////////////////////////////////////////////////////////////////////

    let viewer = null;
    if (previewUrl !== "") {
        viewer =
            <NimbleStandaloneReact
                style={{ height: '100%' }}
                loadUrl={previewUrl}
                frame={globalCurrentFrame[0]}
                playing={playing}
                onPlayPause={(newPlaying) => {
                    setPlaying(newPlaying)
                }}
                onFrameChange={(newFrame) => {
                    globalCurrentFrame[0] = newFrame;
                    if (chartRef.current != null) {
                        chartRef.current.update();
                    }
                    if (frame !== newFrame) {
                        setFrame(newFrame);
                    }
                }}
                backgroundColor={
                    missingGrfArray[globalCurrentFrame[0]] ? '#ffd4db' : '#ffffff'
                }
            />
    }

    let remainingSectionHeight = '50vh';
    let reviewBar = null;
    if (!props.readonly) {
        let reviewButton = null;
        if (segmentContents.reviewFlagExists) {
            reviewButton =
                <button className="btn btn-secondary" onClick={() => {
                    dir.delete(segmentContents.reviewFlagPath).then(() => {
                        setReviewState(home.getReviewStatus(path));
                    });
                }}>Redo Review</button>
                ;
        }
        else {
            reviewButton =
                <button className="btn btn-success" onClick={() => {
                    dir.uploadText(segmentContents.reviewFlagPath, "").then(() => {
                        setReviewState(home.getReviewStatus(path));
                    });
                }}>Finish Review</button>;
        }

        let reviewFrames = [];
        for (let i = 0; i < missingGrfArray.length; i++) {
            let color = missingGrfArray[i] ? 'bg-danger' : 'bg-secondary';
            if (i === frame) {
                color = 'bg-success';
            }
            reviewFrames.push(
                <td key={i}
                    className={color}
                    style={{ height: '100%' }}
                    onMouseOver={() => {
                        if (!draggingFrameWand) {
                            globalCurrentFrame[0] = i;
                            setFrame(i);
                            setPlaying(false);
                        }
                    }}
                    onMouseDown={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const elem = e.target as HTMLTableElement;
                        const parent = elem.parentElement;
                        if (parent == null) {
                            console.error("Got a null parent element for the <td> element. That doesn't make sense, and should never happen!");
                            return;
                        }

                        const boundingRect = parent.getBoundingClientRect();

                        setDraggingFrameWand(true);

                        const dragStartFrame = i;
                        const dragMissingGrf = !missingGrfArray[i];

                        const onMouseMove = action((e: MouseEvent) => {
                            let percentage = (e.clientX - boundingRect.left) / boundingRect.width;
                            if (percentage < 0) {
                                percentage = 0;
                            }
                            if (percentage > 1) {
                                percentage = 1;
                            }
                            let frame = Math.floor(percentage * missingGrfArray.length);
                            if (frame > missingGrfArray.length - 1) {
                                frame = missingGrfArray.length - 1;
                            }

                            const updatedMissingGrfArray = [...missingGrfArray];
                            for (let i = Math.min(frame, dragStartFrame); i <= Math.max(frame, dragStartFrame); i++) {
                                updatedMissingGrfArray[i] = dragMissingGrf;
                                missingGrfArray[i] = dragMissingGrf;
                            }
                            segmentContents.reviewJson.setAttribute('missing_grf_data', updatedMissingGrfArray);

                            globalCurrentFrame[0] = frame;
                            setFrame(frame);
                            setPlaying(false);
                        });

                        const onMouseUp = () => {
                            setDraggingFrameWand(false);
                            window.removeEventListener('mouseup', onMouseUp);
                            window.removeEventListener('mousemove', onMouseMove);
                        };
                        window.addEventListener('mousemove', onMouseMove);
                        window.addEventListener('mouseup', onMouseUp);
                    }}
                    onKeyDown={(e) => {
                        e.preventDefault();
                    }}
                ></td>
            );
        }

        let linkToNext = null;
        if (reviewState.segmentsNeedReview.length > 0) {
            const nextUrl = Session.getDataURL(props.currentLocationUserId, reviewState.segmentsNeedReview[0].path);
            navigateToNext.current = () => {
                setPreviewUrl("");
                navigate(nextUrl);
            }
            linkToNext = <button className="btn btn-primary" style={{ width: '100%' }} onClick={navigateToNext.current}>Review Next Segment</button>
        }
        else {
            const nextUrl = Session.getDataURL(props.currentLocationUserId, segmentContents.parentSubjectPath);
            navigateToNext.current = () => {
                setPreviewUrl("");
                navigate(nextUrl);
            }
            linkToNext = <button className="btn btn-primary" style={{ width: '100%' }} onClick={navigateToNext.current}>Back To Subject</button>
        }

        const urlToReviewRoot = Session.getDataURL(props.currentLocationUserId, reviewState.path);
        const linkToReviewRoot = <Link to={urlToReviewRoot}>{reviewState.path}</Link>;

        if (!segmentContents.reviewFlagExists) {
            reviewBar = <div style={{ height: '80px', width: '100vw', padding: 0, margin: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'row' }}>
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <table style={{ tableLayout: 'fixed', width: 'calc(100% - 20px)', height: 'calc(100% - 10px)' }}>
                            <tr>
                                {reviewFrames}
                            </tr>
                        </table>
                    </div>
                    <div style={{ flex: '0 0 150px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {reviewButton}
                    </div>
                </div>
                <div style={{ flex: '0 0 30px', textAlign: 'center' }}>
                    Reviewed {reviewState.segmentsReviewed.length} of {reviewState.segmentsNeedReview.length + reviewState.segmentsReviewed.length} loaded trial segments under "{linkToReviewRoot}".
                </div>
            </div>;
        }
        else {
            reviewBar = <div style={{ height: '80px', width: '100vw', padding: 0, margin: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'row' }}>
                    <div style={{ flex: '0 0 150px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {reviewButton}
                    </div>
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{linkToNext}</div>;
                </div>
                <div style={{ flex: '0 0 30px', textAlign: 'center' }}>
                    Reviewed {reviewState.segmentsReviewed.length} of {reviewState.segmentsNeedReview.length + reviewState.segmentsReviewed.length} loaded trial segments under "{linkToReviewRoot}".
                </div>
            </div>;
        }

        remainingSectionHeight = 'calc(50vh - 40px)';
    }

    body = (
        <div>
            <div style={{ height: remainingSectionHeight, width: '100vw', padding: 0, margin: 0, overflow: 'hidden' }}>
                {viewer}
            </div>
            <div style={{ height: remainingSectionHeight, width: '100vw', padding: 0, margin: 0, overflow: 'hidden' }}>
                {plot}
            </div>
            {reviewBar}
        </div>
    );

    return body;
});

export default TrialSegmentView;
