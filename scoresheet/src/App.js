import React, { useEffect, useState, useMemo, useRef, useCallback } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    TextField,
  Input,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
} from "@mui/material";
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import styled, { createGlobalStyle } from 'styled-components';
import { DatePicker, LocalizationProvider, PickersDay} from '@mui/x-date-pickers';
import { AdapterDayjs} from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from 'dayjs';
import Badge from '@mui/material/Badge';
import { motion, useAnimation } from "framer-motion";
import {
  applyPatchToPresentationSnapshot,
  applyPatchToRoundSnapshot,
  buildScoresheetPatch,
  createClientId,
  createMutationId,
  hasScoresheetChanges,
  makePresentationSnapshot,
  makeRoundSnapshot,
  shouldIgnoreScoresheetMessage,
} from './sync';
import {
  clearCreatorScoreForRound,
  getDisplayedCreatorBonus,
  getDisplayedFinalTotal,
  getDisplayedJokerBonus,
  getDisplayedRoundScore,
  getSortableFinalTotal,
} from './scoreTotals';
import {
  getCrownTheme,
  getDisplayNameForPlayer,
  getCrownStreak,
  getInheritedCrownedWinner,
  getPlayerFieldForName,
} from './crown';
import { DEFAULT_VISIBLE_PLAYERS } from './defaultPlayers';
import {
  resolveJokerRoundIndices,
  resolvePresentationPlayers,
} from './presentationData';
import {
  buildJokerRouletteSequence,
  JOKER_RANDOMIZE_VALUE,
  pickJokerRouletteIndex,
} from './jokerRoulette';
import {
    extractPlayersFromRounds,
    FIXED_SCORE_FIELDS,
    getDisplayNameForPlayerField,
    getRoundExtraScores,
    getMergedRoundScoreMap,
    getPlayerColor,
    getPlayerStorageKey,
    getPlayerFieldForName as getScoreFieldForName,
    removePlayerFromRound,
} from './playerScores';
import {
    getStylePointTheme,
    getNormalizedStylePoints,
    hasStylePointAward,
    incrementStylePoint,
    setStylePointValue,
} from './stylePoints';

    const basePlayerColorMapping = {
        'score_alex': '#D2042D',
        'score_ichigo': '#ff7f0e',
        'score_megan': '#8e4585',
        'score_zach': '#A020F0',
        'score_jenny': '#ffef00',
        'score_debi': '#8551ff',
        'score_mom': '#8551ff',
        'score_dan': '#560000',
        'score_dad': '#560000',
        'score_chris': '#005427',
        'score_drew': '#8c564b',
        'score_jeff': '#66FF66',
        'score_paige': '#FF6666',
        'score_dillon': '#0000FF',
        'score_tom': '#000042',
        'unknown': '#333333',
    };

    function resolvePlayerColor(playerField) {
      return getPlayerColor(playerField, basePlayerColorMapping);
    }

    const XButton = styled.div`
      width: 20px; // Set the width
      height: 20px; // Set the height
      background-color: ${props => resolvePlayerColor(props.player) || '#000'}; // Dynamic background color
      color: ${props => playerTextColor(resolvePlayerColor(props.player) || '#000000')};  // Set the text color, depending on the background color brightness
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      
      &:hover {
        background-color: ${props => darkenBackground(resolvePlayerColor(props.player) || '#000')};// Darken the background color on hover
      }
    `;

    function playerTextColor(hexColor) {

        // Ensure the hex color starts with '#'
      if (hexColor[0] === '#') {
        hexColor = hexColor.substr(1);
      }

      // Parse the r, g, b values
      const r = parseInt(hexColor.substr(0, 2), 16);
      const g = parseInt(hexColor.substr(2, 2), 16);
      const b = parseInt(hexColor.substr(4, 2), 16);

      // Calculate the brightness
      const brightness = (0.7 * r) + g + (0.3 * b);
      if(brightness < 300) {
            return 'white'
        }
        return 'black'
    }

    // Function to darken the background color on hover
    function darkenBackground(hexColor) {
        if (hexColor[0] === '#') {
            hexColor = hexColor.substr(1);
        }

        // Parse the r, g, b values
        const r = parseInt(hexColor.substr(0, 2), 16);
        const g = parseInt(hexColor.substr(2, 2), 16);
        const b = parseInt(hexColor.substr(4, 2), 16);

        // darken the color by 20%
        const newR = Math.round(r * 0.8);
        const newG = Math.round(g * 0.8);
        const newB = Math.round(b * 0.8);

        const newHexColor = `#${newR.toString(16).padStart(2, '0')}${newG.toString(16).padStart(2, '0')}${newB.toString(16).padStart(2, '0')}`;

        return newHexColor;
    }



    const StyledTableCell = styled(TableCell)`
      background-color: #333;
      && {
        padding: 0.5rem;
        text-align: center;
      }
      div {
          font-size: 1rem;
          font-family: "Monaco";
          padding: 0;
        }
      .textCell {
        color: #fff;
        text-align: center;
        font-family: Monaco;
        font-size: 1rem;
      }
      a {
        color: #fff;
        text-decoration: none;  
        font-family: Monaco;
        font-size: 1rem;
        &:hover {
          color: ${props => resolvePlayerColor(props.player) || '#000'};
        }
      }
    `;


    const StyledTableRow = styled(TableRow)({
      borderBottom: '2px solid #333',
    });

    const StyledButton = styled.button`
        background-color: #1e7662; /* Green */
        border: none;
        color: white;
        padding: 5px 12px;
        margin: 5px;
        text-align: center;
        text-decoration: none;
        font-size: 1rem;
        box-sizing: border-box;
      font-family: "Monaco";
      
      &:hover {
        background-color: ${props => darkenBackground('#1e7662')};// Darken the background color on hover
      }
  `

    const StyledSelect = styled(Select)`
        &&.MuiInputBase-root,
        &&.MuiOutlinedInput-root {
          background-color: #333;
          color: #fff;
          border-radius: 0;
          font-family: "Monaco";
          min-height: 30px;
        }

        && .MuiOutlinedInput-notchedOutline {
          border-color: #1e7662;
        }

        &&:hover .MuiOutlinedInput-notchedOutline {
          border-color: #2c9d84;
        }

        &&.Mui-focused .MuiOutlinedInput-notchedOutline,
        && .Mui-focused .MuiOutlinedInput-notchedOutline {
          border-color: #2c9d84;
        }

        && .MuiSelect-select {
          color: #fff;
          font-size: 0.75rem;
          font-family: "Monaco";
          padding: 0.16rem 1.45rem 0.16rem 0.45rem;
          min-height: unset;
        }

        && .MuiSvgIcon-root {
          color: #fff;
          font-size: 1.05rem;
        }
    `;

    const dropdownMenuProps = {
      PaperProps: {
        sx: {
          backgroundColor: '#333',
          color: '#fff',
          border: '1px solid #1e7662',
          borderRadius: 0,
          boxShadow: '0 12px 26px rgba(0, 0, 0, 0.35)',
          '& .MuiMenuItem-root': {
            fontFamily: 'Monaco, monospace',
            fontSize: '0.8rem',
          },
          '& .MuiMenuItem-root.Mui-selected': {
            backgroundColor: '#1e7662',
          },
          '& .MuiMenuItem-root.Mui-selected:hover': {
            backgroundColor: '#185e4f',
          },
          '& .MuiMenuItem-root:hover': {
            backgroundColor: '#185e4f',
          },
        },
      },
    };

    const StyledFormControl = styled(FormControl)`
        background-color: #333;
        color: #fff;
        max-width: 8rem;
        && * {
          color: #fff;
          font-family: "Monaco";
          font-size: 0.8rem;
          padding: 0.15rem;
          margin: 0rem;
          //margin: 5px 12px;
        }
      `;

    const StyledInputLabel = styled(InputLabel)`
      color: #fff;
      text-align: center;
        font-family: Monaco;
        font-size: 0.8rem;
    `;




    const StyledFormControlLabel = styled(FormControlLabel)`
        background-color: #333;
        color: #fff;
        font-size: 0.8rem;
      && * {
        color: #fff;
        font-family: "Monaco";
        font-size: 0.9rem;
      }
    `;

    const StyledTableContainer = styled(TableContainer)`
        background-color: #333;
        color: #fff;
      
        .showonsmall {
            @media (max-width: 919px) {
              display: block;
            }
            @media (min-width: 920px) {
                display: none;
            }
        }
      `;

    const StyledTextField = styled(TextField)`
      font-family: Monaco;
      color: #fff;
      // prevent wrapping
      div {
          font-size: 12px;
          font-family: "Monaco";
          color: #fff;
          border: none;
          background-color: #333;
          text-align: center;
            white-space: nowrap;
            overflow: hidden;
        }
      
      * {
        font-size: 1rem;
        font-family: "Monaco";
        color: #fff;
      }
      
      div > input {
        color: #fff;
        padding: 0px; 
        margin: 8px 12px;
        font-size: 0.8rem;
        font-family: "Monaco";
        background-color: #333;
      }
      
      && {
        .MuiInputLabel-root {
            color: white;
        }
      }
      
      &:hover {
            background-color: #333;
          border: none;
        }
    `



    const StyledTable = styled(Table)`
      & tbody {
        & tr {
          & .MuiTableCell-root {
            display: none;
    
            @media (min-width: 919px) {
              display: table-cell;
            }
          }
    
          & .MuiTableCell-root:first-child,
          & .MuiTableCell-root:last-child,
          & .MuiTableCell-root:nth-last-child(2),
          & .MuiTableCell-root.selected-column {
            display: table-cell;
          }
        }
      }
      & thead {
        & tr {
          & .MuiTableCell-root {
            display: none;
    
            @media (min-width: 919px) {
              display: table-cell;
            }
          }
    
          & .MuiTableCell-root:first-child,
          & .MuiTableCell-root:last-child,
          & .MuiTableCell-root:nth-last-child(2),
          & .MuiTableCell-root.selected-column {
            display: table-cell;
          }
        }
      }
    `;

    const MetadataSection = styled.div`
      display: flex;
      justify-content: center;
      padding: 0.08rem 0 0.9rem;
    `;

    const MetadataGrid = styled.div`
      width: min(100%, 960px);
      display: grid;
      grid-template-columns: repeat(3, minmax(180px, 220px));
      justify-content: center;
      gap: 0.85rem;
      padding: 0 0.75rem;

      @media (max-width: 919px) {
        grid-template-columns: minmax(0, 1fr);
        width: min(100%, 24rem);
      }
    `;

    const MetadataField = styled.div`
      display: flex;
      flex-direction: column;
      align-items: stretch;
      width: 100%;
    `;

    const MetadataFieldLabel = styled.div`
      color: #fff;
      text-align: center;
      font-family: Monaco;
      font-size: 0.8rem;
      margin-bottom: 0.35rem;
    `;

    const MetadataNotesField = styled(TextField)`
      && {
        width: 100%;
      }

      && .MuiInputBase-root {
        background-color: #333;
        color: #fff;
        font-family: "Monaco";
        border-radius: 0;
        padding: 0;
      }

      && .MuiOutlinedInput-notchedOutline {
        border: none;
      }

      && textarea {
        color: #fff;
        font-family: "Monaco";
        font-size: 0.9rem;
        line-height: 1.4;
        padding: 0.35rem 0.55rem;
        text-align: center;
        white-space: pre-wrap;
      }

      && textarea::placeholder {
        color: rgba(255, 255, 255, 0.5);
        opacity: 1;
        text-align: center;
      }
    `;

    const MetadataFormControl = styled(StyledFormControl)`
      && {
        width: 100%;
        max-width: none;
      }
    `;

    const MetadataNotesFieldWrapper = styled(MetadataField)`
      grid-column: 1 / -1;
      justify-self: center;
      width: min(100%, 680px);
      margin-top: -0.15rem;
    `;

    const MetadataActionField = styled(MetadataField)`
      grid-column: 1 / -1;
      align-items: center;
    `;

    const MetadataActionRow = styled.div`
      width: 100%;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    `;

    const MetadataActionButtons = styled.div`
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 0.55rem;
      flex-wrap: wrap;
    `;

    const MetadataActionPrimaryButton = styled(StyledButton)`
      margin: 0;
      min-width: 210px;
    `;

    const PlayerNameStack = styled.div`
      display: flex;
      justify-content: center;
    `;

    const PlayerNameAnchor = styled.span`
      position: relative;
      display: inline-flex;
      align-items: flex-start;
      justify-content: center;
      padding-top: 0.1rem;
    `;

    const WinnerCrown = styled(motion.div)`
      width: 20px;
      height: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: absolute;
      top: -0.56rem;
      right: -0.58rem;
      pointer-events: none;
      transform-origin: left bottom;
      z-index: 1;
    `;

    const StylePointShades = styled(motion.div)`
      width: 28px;
      height: 18px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: absolute;
      top: -0.46rem;
      left: -0.8rem;
      pointer-events: none;
      transform-origin: center;
      z-index: 1;
    `;

      const GlobalStyle = createGlobalStyle`
          .MuiPopover-root .MuiPaper-root {
            display: block;
          }
    `;

function CrownIcon({ streak }) {
  const theme = getCrownTheme(Math.max(streak, 1));

  return (
    <svg viewBox="0 0 24 18" width="20" height="16" aria-hidden="true">
      <path
        d="M2 15L4.6 5.5L9.2 10.2L12 2.5L14.8 10.2L19.4 5.5L22 15H2Z"
        fill={theme.fill}
        stroke={theme.stroke}
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <rect x="2.5" y="15" width="19" height="2" rx="1" fill={theme.base} />
      <path d="M4.1 13.6H19.9" stroke={theme.trim} strokeWidth="1" strokeLinecap="round" opacity="0.95" />
      <circle cx="4.6" cy="5.5" r="1.2" fill={theme.leftGem} />
      <circle cx="12" cy="2.5" r="1.2" fill={theme.centerGem} />
      <circle cx="19.4" cy="5.5" r="1.2" fill={theme.rightGem} />
      {streak === 2 && (
        <>
          <path d="M6.2 4.5L6.9 5.6L8.1 5.9L7.2 6.8L7.3 8.1L6.2 7.5L5 8.1L5.2 6.8L4.3 5.9L5.5 5.6Z" fill={theme.sparkle} opacity="0.95" />
          <path d="M17.8 4.2L18.4 5.1L19.4 5.4L18.6 6.2L18.8 7.3L17.8 6.8L16.8 7.3L17 6.2L16.2 5.4L17.2 5.1Z" fill={theme.sparkle} opacity="0.92" />
          <path d="M8.1 14.5L9.5 13.2" stroke={theme.accent} strokeWidth="0.9" strokeLinecap="round" />
          <path d="M15.9 14.5L14.5 13.2" stroke={theme.accent} strokeWidth="0.9" strokeLinecap="round" />
        </>
      )}
      {streak >= 3 && (
        <>
          <path d="M6.1 11.8H17.9" stroke={theme.accent} strokeWidth="1" strokeLinecap="round" opacity="0.95" />
          <circle cx="8.7" cy="9.2" r="0.85" fill={theme.leftGem} />
          <circle cx="15.3" cy="9.2" r="0.85" fill={theme.rightGem} />
        </>
      )}
      {streak >= 4 && (
        <>
          <path d="M12 0.9L13.1 2.4L14.7 2.9L13.5 4.1L13.8 5.8L12 4.9L10.2 5.8L10.5 4.1L9.3 2.9L10.9 2.4Z" fill={theme.sparkle} opacity="0.98" />
          <path d="M5.7 4.7L6.3 5.6L7.4 5.9L6.6 6.7L6.7 7.8L5.7 7.3L4.7 7.8L4.8 6.7L4 5.9L5.1 5.6Z" fill={theme.sparkle} opacity="0.95" />
          <path d="M18.3 4.7L18.9 5.6L20 5.9L19.2 6.7L19.3 7.8L18.3 7.3L17.3 7.8L17.4 6.7L16.6 5.9L17.7 5.6Z" fill={theme.sparkle} opacity="0.95" />
          <path d="M7.1 12.6L12 8.8L16.9 12.6" stroke={theme.trim} strokeWidth="0.85" strokeLinecap="round" opacity="0.9" />
        </>
      )}
    </svg>
  );
}

function SunglassesIcon({ theme }) {
  return (
    <svg viewBox="0 0 34 24" width="28" height="18" aria-hidden="true">
      {theme?.flame && (
        <>
          <path
            d="M4.7 12.4C3.8 8.9 6 5.9 8.8 4.3C9.4 6.3 10.6 7.7 11 9.5C11.4 11.8 10.1 13.8 7.8 14.5C6.3 14.1 5.1 13.4 4.7 12.4Z"
            fill={theme.flameOuter}
            opacity="0.92"
          />
          <path
            d="M10.8 8.2C10 4.3 12.5 1.3 15.8 0.4C16.4 2.8 17.7 4.6 18.1 6.7C18.6 9.8 16.8 12.2 13.8 12.8C12.4 11.7 11.3 10.1 10.8 8.2Z"
            fill={theme.flameOuter}
            opacity="0.98"
          />
          <path
            d="M18.1 7.3C17.5 4 19.6 1.6 22.6 0.8C23 3 24.2 4.7 24.7 6.5C25.3 9.3 23.8 11.7 21 12.3C19.7 11.3 18.7 9.6 18.1 7.3Z"
            fill={theme.flameOuter}
            opacity="0.96"
          />
          <path
            d="M25 12C24.4 9.1 26.1 6.5 28.8 5.2C29.3 7 30.2 8.5 30.6 10C31 12.2 29.6 14.1 27.4 14.6C26.2 14.1 25.4 13.1 25 12Z"
            fill={theme.flameOuter}
            opacity="0.9"
          />
          <path
            d="M13.9 8C13.7 6.2 14.6 4.8 16 4.1C16.4 5.2 17 6.1 17.2 7.2C17.5 8.8 16.6 10 15 10.3C14.4 9.7 14 9 13.9 8Z"
            fill={theme.flameCore}
          />
          <path
            d="M21.8 7.2C21.5 5.6 22.4 4.3 23.7 3.7C24 4.8 24.6 5.6 24.9 6.6C25.2 8 24.4 9.1 23 9.4C22.5 8.8 22 8.1 21.8 7.2Z"
            fill={theme.flameCore}
          />
        </>
      )}
      <path d="M3.8 12.1L6.9 13.6" stroke={theme.frameStroke} strokeWidth="1.8" strokeLinecap="round" />
      <path d="M27.1 13.6L30.2 12.1" stroke={theme.frameStroke} strokeWidth="1.8" strokeLinecap="round" />
      <rect x="6.3" y="10.6" width="10.2" height="7.2" rx="2.5" fill={theme.frameFill} stroke={theme.frameStroke} strokeWidth="1.35" />
      <rect x="17.5" y="10.6" width="10.2" height="7.2" rx="2.5" fill={theme.frameFill} stroke={theme.frameStroke} strokeWidth="1.35" />
      <rect x="6.3" y="10.6" width="10.2" height="7.2" rx="2.5" fill="none" stroke={theme.rimHighlight} strokeWidth="0.65" opacity="0.95" />
      <rect x="17.5" y="10.6" width="10.2" height="7.2" rx="2.5" fill="none" stroke={theme.rimHighlight} strokeWidth="0.65" opacity="0.95" />
      <rect x="7.2" y="11.3" width="8.4" height="5.8" rx="1.8" fill="#050505" />
      <rect x="18.4" y="11.3" width="8.4" height="5.8" rx="1.8" fill="#050505" />
      <rect x="15.7" y="12.3" width="2.7" height="1.8" rx="0.9" fill={theme.frameStroke} />
      {theme?.sparkle && (
        <>
          <path d="M8.6 9.7L9.1 10.8L10.3 11.1L9.4 11.9L9.6 13.1L8.6 12.5L7.5 13.1L7.7 11.9L6.8 11.1L8 10.8Z" fill={theme.sparkleColor} opacity="0.9" />
          <path d="M24.7 9L25.2 10L26.2 10.3L25.4 11L25.6 12L24.7 11.5L23.8 12L24 11L23.2 10.3L24.2 10Z" fill={theme.sparkleColor} opacity="0.85" />
        </>
      )}
    </svg>
  );
}

const PlayerTable = () => {
    const defaultHost = 'Alex';
    const defaultPlayers = useMemo(() => {
      return [...DEFAULT_VISIBLE_PLAYERS];
    }, []);

    const [rounds, setRounds] = useState([]);
    const [players, setPlayers] = useState(defaultPlayers);
    const [selectedRounds, setSelectedRounds] = useState(
        players.reduce((acc, curr) => ({...acc, [curr]: ''}), {})
    );
    const [roundCreators, setRoundCreators] = useState({});
    const [scores, setScores] = useState({});
    const [medianScores, setMedianScores] = useState([]);
    const [isSortAscending, setIsSortAscending] = useState(true);
    const [dates, setDates] = useState([]);
    const sortedDates = useMemo(() => {
                                return [...dates].sort().reverse(); // or any other sorting logic you have
                            }, [dates]);
    const [selectedDate, setSelectedDate] = useState('');
    const [textColor] = useState('black');
    const [isDatesInitialized, setIsDatesInitialized] = useState(false);
    const [newPlayerName, setNewPlayerName] = useState('');
    const [cooperativeStatus, setCooperativeStatus] = useState({});
    const [majorCategories, setMajorCategories] = useState([]);
    const [selectedMajorCategories, setSelectedMajorCategories] = useState('');
    const [minor1Categories, setMinor1Categories] = useState([]);
    const [selectedMinor1Categories, setSelectedMinor1Categories] = useState('');
    const [minor2Categories, setMinor2Categories] = useState([]);
    const [selectedMinor2Categories, setSelectedMinor2Categories] = useState('');
    const [isBottomRowVisible, setIsBottomRowVisible] = useState(false);
    const [isReplay, setIsReplay] = useState(false);
    const [maxScores, setMaxScores] = useState({});
    const [allPlayers, setAllPlayers] = useState([]);
    const [isSaved, setIsSaved] = useState(true);
    const [presID, setPresID] = useState(0);
    const [tempTitles, setTempTitles] = useState([]);
    const [tempLinks, setTempLinks] = useState([]);
    const [selectedColumnIndex, setSelectedColumnIndex] = useState(1);
    const [updateFlag, setUpdateFlag] = useState(0); // Update flag
    const [prevUpdateFlag, setPrevUpdateFlag] = useState(0); // Previous update flag
    const [saveRequestCount, setSaveRequestCount] = useState(0);
    const [openDatePicker, setOpenDatePicker] = useState(false);
    // ANIMATION STUFF
    const [showPic, setShowPic] = useState(false);
    const playerControls = useAnimation();
    const [host, setHost] = useState(defaultHost);
    const [scorekeeper, setScorekeeper] = useState(defaultHost);
    const [tiebreakWinner, setTiebreakWinner] = useState('');
    const [crownedWinner, setCrownedWinner] = useState('');
    const [inheritedCrownedWinner, setInheritedCrownedWinner] = useState('');
    const [presentations, setPresentations] = useState([]);
    const [notes, setNotes] = useState('');
    const [stylePoints, setStylePoints] = useState({}); // { Alex: 1.0, Ichigo: 0.5, ... }
    const [isStylePointDialogOpen, setIsStylePointDialogOpen] = useState(false);
    const [selectedStylePointPlayer, setSelectedStylePointPlayer] = useState('');
    const [isTiebreakDialogOpen, setIsTiebreakDialogOpen] = useState(false);
    const [selectedTiebreakPlayer, setSelectedTiebreakPlayer] = useState('');
    const [jokerRouletteHighlights, setJokerRouletteHighlights] = useState({});
    const [jokerRouletteSpinningPlayers, setJokerRouletteSpinningPlayers] = useState({});

    const playerNamesDisplay = useMemo(
      () => (players || []).map(getDisplayNameForPlayerField),
      [players]
    );

    const creatorOptions = useMemo(
      () => [...new Set([...(allPlayers || []), ...playerNamesDisplay])].sort((left, right) => left.localeCompare(right)),
      [allPlayers, playerNamesDisplay],
    );


    const pulsePlayer = useCallback(async () => {
      await playerControls.start({
        scale: [1, 1.2, 1],           // grow → shrink once
        transition: { duration: 0.8, ease: "easeInOut" },
      });
    }, [playerControls]);


    const theme = useTheme();
    const isSmallScreen = useMediaQuery(theme.breakpoints.down('sm'));

    // let url = "http://localhost:8000"
    let url = "https://hailsciencetrivia.com"

    const wsRef = useRef(null);
    const pingIntervalRef = useRef(null);
    const clientIdRef = useRef(createClientId());
    const pendingMutationIdsRef = useRef(new Set());
    const serverRoundSnapshotRef = useRef({});
    const serverPresentationSnapshotRef = useRef(makePresentationSnapshot(null));
    const stylePointAnchorRefs = useRef({});
    const newPlayerInputRef = useRef(null);
    const datePickerFieldRef = useRef(null);
    const jokerRouletteTimeoutsRef = useRef({});
    const saveInFlightRef = useRef(false);
    const saveQueuedRef = useRef(false);
    const latestStateRef = useRef(null);
    const presentationHydrationKeyRef = useRef('');
    const isVisible = usePageVisibility();
    const websocketUrl = `${url.replace(/^http/, 'ws')}/ws/scoresheet/`;

    const markDirty = useCallback(() => {
      setIsSaved(false);
      setSaveRequestCount(prev => prev + 1);
    }, []);

    const clearJokerRouletteForPlayer = useCallback((player) => {
      const playerTimeouts = jokerRouletteTimeoutsRef.current[player] || [];
      playerTimeouts.forEach(timeoutId => {
        window.clearTimeout(timeoutId);
      });
      delete jokerRouletteTimeoutsRef.current[player];

      setJokerRouletteHighlights(prevState => {
        if (!(player in prevState)) {
          return prevState;
        }
        const nextState = { ...prevState };
        delete nextState[player];
        return nextState;
      });

      setJokerRouletteSpinningPlayers(prevState => {
        if (!(player in prevState)) {
          return prevState;
        }
        const nextState = { ...prevState };
        delete nextState[player];
        return nextState;
      });
    }, []);

    const clearAllJokerRoulette = useCallback(() => {
      Object.keys(jokerRouletteTimeoutsRef.current).forEach(player => {
        const playerTimeouts = jokerRouletteTimeoutsRef.current[player] || [];
        playerTimeouts.forEach(timeoutId => {
          window.clearTimeout(timeoutId);
        });
      });
      jokerRouletteTimeoutsRef.current = {};
      setJokerRouletteHighlights({});
      setJokerRouletteSpinningPlayers({});
    }, []);

    const sortedPlayersForDisplay = useMemo(
      () => [...players].sort((b, a) => {
        const totalScoreA = getSortableFinalTotal(rounds, scores, a, selectedRounds[a], medianScores);
        const totalScoreB = getSortableFinalTotal(rounds, scores, b, selectedRounds[b], medianScores);

        return isSortAscending ? totalScoreA - totalScoreB : totalScoreB - totalScoreA;
      }),
      [players, rounds, scores, selectedRounds, medianScores, isSortAscending],
    );

    const crownedPlayer = useMemo(() => {
      const activeCrownedWinner = crownedWinner || inheritedCrownedWinner;
      return getPlayerFieldForName(players, activeCrownedWinner);
    }, [crownedWinner, inheritedCrownedWinner, players]);

    const crownStreak = useMemo(
      () => getCrownStreak(
        presentations,
        selectedDate,
        crownedWinner || inheritedCrownedWinner,
        crownedWinner,
      ),
      [crownedWinner, inheritedCrownedWinner, presentations, selectedDate],
    );

    function convertDate(dateStr) {
        const [month, day, year] = dateStr.split('.');
        return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
    }


    function getFontSize(textLength) {
        if (textLength.length < 9) {
          return '1.1rem'; // Default font size
        } else if (textLength.length < 18) {
          return '1rem'; // Smaller font size for text length between 10 and 20
        } else if (textLength.length < 27) {
          return '0.9rem'; // Smaller font size for text length between 10 and 20
        } else if (textLength.length < 80) {
          return '0.8rem'; // Even smaller font size for text length 20 and above
        } else {
            return '0.6rem'; // Even smaller font size for text length 20 and above
        }
      };

    useEffect(() => {
       console.log("isSaved updated:", isSaved);
    }, [isSaved]);

    function getCookie(name) {
    let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            let cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                let cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    let csrfToken = getCookie('csrftoken');

    useEffect(() => {
        fetch(url + '/api-token-auth/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken   // Add the CSRF token here
            },
            body: JSON.stringify({
                username: "Alex",
                password: "Rapt0rpusia",
            }),
        })
            .then(response => response.json())
            .then(data => {
                if (data.token) {
                    // Save the token somewhere (e.g., local storage)
                    localStorage.setItem('token', data.token);
                } else {
                    // Handle login failure
                }
            })
            .catch((error) => {
                console.error('Error:', error);
            });
    }, [csrfToken, url]);

    useEffect(() => {
      fetch(url + '/api/v1/trivia-rounds/', {
            headers: {
                'Authorization': `Token ${localStorage.getItem('token')}`,
            },
        })
        .then(response => {
          console.log('Initial response: ', response);
          if (!response.ok) {
            throw new Error("HTTP error " + response.status);
          }
          return response.json();
        })
        .then(json => {
            const majorCategoryValues = json.map(item => item.major_category);
            const minor1CategoryValues = json.map(item => item.minor_category1);
            const minor2CategoryValues = json.map(item => item.minor_category2);
            const allPlayers = json.map(item => getDisplayNameForPlayerField(item.creator));
            // Get unique values by converting to a Set and then back to an Array
            const uniqueMajorCategories = [...new Set(majorCategoryValues)];
            // let the minor categories include the major categories as well
            const uniqueMinor1Categories = [...new Set(minor1CategoryValues), ...new Set(minor2CategoryValues), ...uniqueMajorCategories];
            const uniqueMinor2Categories = [...new Set(minor1CategoryValues), ...new Set(minor2CategoryValues), ...uniqueMajorCategories];
            // let's turn these into sets and then back into arrays to remove duplicates
            const uniqueMinor1CategoriesSet = new Set(uniqueMinor1Categories);
            const uniqueMinor2CategoriesSet = new Set(uniqueMinor2Categories);
            // now back to arrays
            const finalUniqueMinor1Categories = [...uniqueMinor1CategoriesSet];
            const finalUniqueMinor2Categories = [...uniqueMinor2CategoriesSet];

            const uniquePlayers = [...new Set(allPlayers)];
            // reset page load flag

            setAllPlayers(uniquePlayers);
            setMajorCategories(uniqueMajorCategories);
            setMinor1Categories(finalUniqueMinor1Categories);
            setMinor2Categories(finalUniqueMinor2Categories);
          console.log(json);
          // before setting the rounds, filter out all rounds that are not from the date march 18th, 2020.
            // only set the dates if they haven't been set yet
            if (dates.length === 0) {
                const uniqueDates = [...new Set(json.map(item => item.date))];
                setDates(uniqueDates);
            }
            json = json.filter(round => round.date === selectedDate);
            const nextRoundSnapshot = {};
            json.forEach(round => {
              nextRoundSnapshot[round.id] = makeRoundSnapshot(round);
            });
            serverRoundSnapshotRef.current = nextRoundSnapshot;
          setRounds(json);

          // set tempTitles if it hasn't been set yet
            if (tempTitles.length === 0 || prevUpdateFlag !== updateFlag) {
                let initialTempTitles = [];
                json.forEach(round => {
                    initialTempTitles.push(round.title);
                });
                setTempTitles(initialTempTitles);
            }

            // set tempLinks if it hasn't been set yet
            if (tempLinks.length === 0 || prevUpdateFlag !== updateFlag) {
                let initialTempLinks = [];
                json.forEach(round => {
                    initialTempLinks.push(round.link);
                });
                setTempLinks(initialTempLinks);
            }

            setPrevUpdateFlag(updateFlag);


          let initialCooperativeStatus = {};
            json.forEach(round => {
              initialCooperativeStatus[round.title] = round.cooperative || false;
            });
            setCooperativeStatus(initialCooperativeStatus);

            let initialReplayStatus = {};
            json.forEach(round => {
                initialReplayStatus[round.title] = round.replay || false;
            });
            setIsReplay(initialReplayStatus);

            // also set the initial Major Categories
            let initialMajorCategories = {};
            json.forEach(round => {
                initialMajorCategories[round.title] = round.major_category || '';
            });
            setSelectedMajorCategories(initialMajorCategories);

            // also set the initial Minor Categories
            let initialMinor1Categories = {};
            json.forEach(round => {
                initialMinor1Categories[round.title] = round.minor_category1 || '';
            });
            setSelectedMinor1Categories(initialMinor1Categories);

            // also set the initial Minor Categories
            let initialMinor2Categories = {};
            json.forEach(round => {
                initialMinor2Categories[round.title] = round.minor_category2 || '';
            });
            setSelectedMinor2Categories(initialMinor2Categories);

            // also set the initial Max Scores
            let initialMaxScores = {};
            json.forEach(round => {
                initialMaxScores[round.title] = round.max_score || 10;
            });
            setMaxScores(initialMaxScores);

          let roundCreators = {};
            for (let round of json) {
              roundCreators[round.title] = round.creator;
            }
            // in the roundCreators object, replace the values "Dad" and "Mom" with "Dan" and "Debi", respectively
            roundCreators = Object.keys(roundCreators).reduce((acc, key) => {
                if (roundCreators[key] === 'Dad') {
                    acc[key] = 'Dan';
                } else if (roundCreators[key] === 'Mom') {
                    acc[key] = 'Debi';
                } else {
                    acc[key] = roundCreators[key];
                }
                return acc;
            }, {});
            setRoundCreators(roundCreators);

          // start by setting the playerNames to the default players
            let playerNames = [...defaultPlayers, ...extractPlayersFromRounds(json)];

          // Get unique player names
          playerNames = [...new Set(playerNames)];
          // setPlayers(playerNames);

          const initialScores = {};
          playerNames.forEach(player => {
            initialScores[player] = {};
            json.forEach(round => {
              initialScores[player][round.title] = getMergedRoundScoreMap(round)[player] ?? null;
            });
          });
          setScores(initialScores);
        })
        .catch(function() {
            //setErrorMessage("Failed to fetch rounds");
        });
    }, [selectedDate, defaultPlayers, dates.length, tempTitles.length, tempLinks.length, url, updateFlag]);

    useEffect(() => {
        const hydrationKey = `${selectedDate}:${updateFlag}`;
        const shouldHydrateFromServer =
          isSavedRef.current || presentationHydrationKeyRef.current !== hydrationKey;

        if (!shouldHydrateFromServer) {
            return undefined;
        }

        let isCancelled = false;

        fetch(url + '/api/v1/presentations/', {
            headers: {
                'Authorization': `Token ${localStorage.getItem('token')}`,
            },
        })
        .then(response => {
          console.log('Initial response: ', response);
          if (!response.ok) {
            throw new Error("HTTP error " + response.status);
          }
          return response.json();
        })
        .then(json => {
            if (isCancelled) {
                return;
            }
            if (!isSavedRef.current && presentationHydrationKeyRef.current === hydrationKey) {
                return;
            }

            presentationHydrationKeyRef.current = hydrationKey;
            setPresentations(json);
            // strip the score_ prefix from the player names
            const selectedPresentation = json.find(presentation => convertDate(presentation.name) === selectedDate)
            serverPresentationSnapshotRef.current = makePresentationSnapshot(selectedPresentation);
            // const playerList = selectedPresentation.player_list;

            // start by setting the playerNames to the default players

            // let playerNames = [];
            // if (playerList) {
            //     console.log('playerList:', playerList);
            //     playerNames = [...playerList];
            // }
            // else {
            //     playerNames = [...defaultPlayers];
            //     for (let round of json) {
            //         for (let key of Object.keys(round)) {
            //             if (key.startsWith('score_') && round[key] !== 0 && round[key] !== null) {
            //                 playerNames.push(key);
            //             }
            //         }
            //     }
            // }

          // Get unique player names
          // playerNames = [...new Set(playerNames)];
          // setPlayers(playerNames);
            // get all the playernames via selectedPresentation.player_list
            // the format of the player_list is ["score_alex": "score_alex", "score_dan":"score_day", ...]
            // so we need to extract the keys from the object i.e. "Alex", "Dan", etc.
            // start by converting player_list from a string to an object

            let plist = null;
            if(selectedPresentation) {
                plist = selectedPresentation.player_list;
            }
            const resolvedPlayers = [...new Set([
                ...resolvePresentationPlayers(plist, defaultPlayers),
                ...extractPlayersFromRounds(rounds),
            ])];
            setPlayers(resolvedPlayers);


            if(selectedPresentation) {
                const jokerRoundIndices = resolveJokerRoundIndices(selectedPresentation.joker_round_indices);
                // const jokerRoundIndices = selectedPresentation.joker_round_indices;
                const ID = selectedPresentation.presentation_id;

                setPresID(ID);

                setPresID(ID);

                // hydrate meta
                setHost(selectedPresentation.host || defaultHost);
                setScorekeeper(selectedPresentation.scorekeeper || defaultHost);
                setTiebreakWinner(selectedPresentation.tiebreak_winner || '');
                setCrownedWinner(selectedPresentation.crowned_winner || '');
                setInheritedCrownedWinner(getInheritedCrownedWinner(json, selectedDate));
                setNotes(selectedPresentation.notes || '');

                // style_points may arrive as object or stringified JSON
                let sp = selectedPresentation.style_points;
                try {
                  if (typeof sp === 'string' && sp.trim()) sp = JSON.parse(sp.replace(/'/g,'"'));
                } catch(e){ sp = {}; }
                setStylePoints(getNormalizedStylePoints(sp || {}));


                const initialSelectedRoundsWithPrefix = resolvedPlayers.reduce((acc, playerField) => {
                    const playerKey = getPlayerStorageKey(playerField);
                    if (playerKey && jokerRoundIndices[playerKey]) {
                        acc[playerField] = jokerRoundIndices[playerKey];
                    }
                    return acc;
                }, {});

                setSelectedRounds(initialSelectedRoundsWithPrefix);
            } else {
                console.log("No presentation found for date: ", selectedDate);
                setHost(defaultHost);
                setScorekeeper(defaultHost);
                setTiebreakWinner('');
                setCrownedWinner('');
                setInheritedCrownedWinner(getInheritedCrownedWinner(json, selectedDate));
                setNotes('');
                setStylePoints({});
                setSelectedRounds(resolvedPlayers.reduce((acc, curr) => ({...acc, [curr]: "Select"}), {}));
                setPresID(0);
            }
        })
        .catch(error => {
            if (isCancelled) {
                return;
            }
            console.error('Error fetching presentations:', error);
        });

        return () => {
            isCancelled = true;
        };
    }, [defaultHost, selectedDate, updateFlag, url]);

    useEffect(() => {
      if (players.length > 0 && rounds.length > 0) {

        // Compute median scores
        const medianScores = rounds.map(round => {
            const transformedCreatorName = transformName(round.creator);
            const formattedName = getScoreFieldForName(transformedCreatorName);
            if (players.includes(formattedName)) {
                const scores = Object.entries(getMergedRoundScoreMap(round))
                  .filter(([scoreKey, scoreValue]) => formattedName !== scoreKey && typeof scoreValue === 'number')
                  .map(([, scoreValue]) => scoreValue);

                scores.sort((a, b) => a - b);

                let median;
                if (scores.length % 2 === 0) { // even length
                  median = (scores[scores.length / 2 - 1] + scores[scores.length / 2]) / 2;
                } else { // odd length
                  median = scores[Math.floor(scores.length / 2)];
            }

            return median;
          } else {
            return null;
          }
        });
        setMedianScores(medianScores);
      }
    }, [players, rounds, roundCreators]);

    useEffect(() => {
        console.log('sortedDates:', sortedDates);

      if (dates.length > 0 && !isDatesInitialized) {
        setSelectedDate(sortedDates[0]);
        setIsDatesInitialized(true);
      }
    }, [dates, isDatesInitialized, sortedDates]);

    const isSavedRef = useRef(isSaved);

    useEffect(() => {
       isSavedRef.current = isSaved;
    }, [isSaved]);

    useEffect(() => {
      latestStateRef.current = {
        rounds,
        selectedRounds,
        roundCreators,
        scores,
        players,
        host,
        scorekeeper,
        tiebreakWinner,
        crownedWinner,
        notes,
        stylePoints,
        selectedMajorCategories,
        selectedMinor1Categories,
        selectedMinor2Categories,
        cooperativeStatus,
        isReplay,
        maxScores,
        selectedDate,
        presID,
      };
    }, [
      cooperativeStatus,
      host,
      isReplay,
      maxScores,
      notes,
      players,
      presID,
      roundCreators,
      rounds,
      scorekeeper,
      scores,
      selectedDate,
      selectedMajorCategories,
      selectedMinor1Categories,
      selectedMinor2Categories,
      selectedRounds,
      stylePoints,
      tiebreakWinner,
      crownedWinner,
    ]);

    function usePageVisibility() {
        const [isVisible, setIsVisible] = useState(!document.hidden);

        useEffect(() => {
            const handleVisibilityChange = () => {
                setIsVisible(!document.hidden);
            };

            document.addEventListener('visibilitychange', handleVisibilityChange);

            return () => {
                document.removeEventListener('visibilitychange', handleVisibilityChange);
            };
        }, []);

        return isVisible;
    }

    useEffect(() => {
        // if isSaved is true, skip
        const handleBeforeUnload = (e) => {
            if (!isSavedRef.current) {
                e.preventDefault();
                e.returnValue = "You have unsaved changes! Are you sure you want to leave?";
            }
        };

        window.addEventListener('beforeunload', handleBeforeUnload);

        // Cleanup the event listener when the component unmounts
        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload);
        };
    }, []);

    useEffect(() => {
        if (isVisible) {
            if ( !wsRef.current || wsRef.current.readyState === WebSocket.CLOSED ){
                setUpdateFlag(prev => prev + 1); // Increment the flag to trigger re-fetch
            }
            if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
                wsRef.current = new WebSocket(websocketUrl);

                wsRef.current.onopen = () => {
                    console.log('Connected to the WebSocket');
                    if (pingIntervalRef.current) {
                        clearInterval(pingIntervalRef.current);
                    }
                    pingIntervalRef.current = setInterval(() => {
                        if (wsRef.current.readyState === WebSocket.OPEN) {
                            wsRef.current.send(JSON.stringify({type: 'ping'}));
                        }
                    }, 30000);
                };

                wsRef.current.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    if (data.type === 'pong') {
                        return;
                    }

                    if (!data.message) {
                        console.log('WebSocket message received with no payload:', data);
                        return;
                    }

                    console.log('WebSocket message received:', data.message);

                    if (shouldIgnoreScoresheetMessage(data.message, clientIdRef.current, pendingMutationIdsRef.current)) {
                        pendingMutationIdsRef.current.delete(data.message.mutation_id);
                        return;
                    }

                    if (data.message && data.message.action === 'update') {
                        console.log('Received update message')
                        setUpdateFlag(prev => prev + 1); // Increment the flag to trigger re-fetch
                        console.log('Update flag incremented');
                    }
                };

                wsRef.current.onerror = (error) => {
                    console.error('WebSocket error:', error);
                };

                wsRef.current.onclose = () => {
                    console.log('Disconnected from the WebSocket');
                    if (pingIntervalRef.current) {
                        clearInterval(pingIntervalRef.current);
                        pingIntervalRef.current = null;
                    }
                };

                // Cleanup function for WebSocket
                return () => {
                    if (pingIntervalRef.current) {
                        clearInterval(pingIntervalRef.current);
                        pingIntervalRef.current = null;
                    }
                    if (wsRef.current) {
                        wsRef.current.close();
                        wsRef.current = null;
                    }
                };
            }
        }
    }, [isVisible, websocketUrl]);

    const handleScoreChange = (event, player, roundTitle, round) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;

        const inputValue = event.target.innerText;
        let newScore;

        // Check if input is an empty string
        if (inputValue.trim() === '') {
            newScore = null;  // You can also use null or undefined, depending on your preference
        } else {
            newScore = parseFloat(inputValue);
        }

        if (!isNaN(newScore)) {
            const updatedRounds = [...rounds];
            const roundIndex = updatedRounds.findIndex(r => r.id === round.id);
            if (roundIndex !== -1) {
                updatedRounds[roundIndex][player] = newScore;
                if (!FIXED_SCORE_FIELDS.includes(player)) {
                    const nextExtraScores = { ...getRoundExtraScores(updatedRounds[roundIndex]) };
                    if (newScore === null) {
                        delete nextExtraScores[player];
                    } else {
                        nextExtraScores[player] = newScore;
                    }
                    updatedRounds[roundIndex].extra_scores = nextExtraScores;
                }
                setRounds(updatedRounds);
            }
        }

        setScores({
            ...scores,
            [player]: {
                ...scores[player],
                [roundTitle]: newScore,
            },
        });
        markDirty();
    };


    const handleRemovePlayer = (playerToRemove) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;

      const displayName = getDisplayNameForPlayerField(playerToRemove);
      clearJokerRouletteForPlayer(playerToRemove);

      setPlayers(prevPlayers => prevPlayers.filter(player => player !== playerToRemove));
      setRounds(prevRounds => prevRounds.map(round => removePlayerFromRound(round, playerToRemove)));
      setScores(prevScores => {
        const nextScores = { ...prevScores };
        delete nextScores[playerToRemove];
        return nextScores;
      });
      setSelectedRounds(prevSelectedRounds => {
        const nextSelectedRounds = { ...prevSelectedRounds };
        delete nextSelectedRounds[playerToRemove];
        return nextSelectedRounds;
      });
      setStylePoints(prevStylePoints => setStylePointValue(prevStylePoints, displayName, ''));
      markDirty();
    };

    const handleChangeDate = (eventOrDate) => {
        const nextDate =
          typeof eventOrDate === 'string'
            ? eventOrDate
            : eventOrDate?.target?.value;

        if (!nextDate) {
            return;
        }

        // console.log('sortedDates:', sortedDates);

        if (!isSaved) {
            const confirmChange = window.confirm("Are you sure you want to change the date? You have unsaved changes.");
            if (!confirmChange) return;
        }

        if (nextDate !== selectedDate) {
            clearAllJokerRoulette();
            // check if the eventOrDate.target.value exists in the sorted dates array
            // and if it doesn't run:
            //  setSelectedDate(todayStr);
            //  setTempTitles([]);
            //  setPresID(0);

            if (!sortedDates.includes(nextDate)) {
                // setDates(prevDates => [...prevDates, eventOrDate.target.value]);
                setSelectedDate(nextDate);
                setTempTitles([]);
                setTempLinks([]);
                setPresID(0);
                return;
            }

            setSelectedDate(nextDate);
            const filteredRounds = rounds.filter(round => round.date === nextDate);
            setRounds(filteredRounds);
            let initialTempTitles = [];
            filteredRounds.forEach(round => {
                initialTempTitles.push(round.title);
            });
            setTempTitles(initialTempTitles);

            let initialTempLinks = [];
            filteredRounds.forEach(round => {
                initialTempLinks.push(round.link);
            });
            setTempLinks(initialTempLinks);
        }

        // else {
        //     // if the currently selected date is already today, don't do anything
        //     let currentDateString = selectedDate;
        //     let currentDate = new Date(currentDateString);
        //     // log the date string
        //     console.log('currentDateString:', currentDateString);
        //     const today = new Date();
        //     const dateString = today.toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' });
        //
        //     // Splitting the dateString into year, month, and day
        //     // log the date string
        //     console.log('dateString:', dateString);
        //     const parts = dateString.split('-');
        //     const year = parts[0];
        //     const month = parts[1].padStart(2, '0'); // Ensuring two digits
        //     const day = parts[2].padStart(2, '0');   // Ensuring two digits
        //
        //     const todayStr = `${year}-${month}-${day}`;
        //
        //     if (currentDate.getFullYear() === parseInt(year) && currentDate.getMonth() + 1 === parseInt(month) && currentDate.getDate() === parseInt(day)) {
        //         return;
        //     }
        //     setDates(prevDates => [...prevDates, todayStr]);
        //         setSelectedDate(todayStr);
        //         setTempTitles([]);
        //         setPresID(0);
        // }
    }

    const confirmPastChange = () => {
        let currentDateString = selectedDate;
        let currentDate = new Date(currentDateString);

        const today = new Date();
        const dateString = today.toLocaleDateString('en-CA', { timeZone: 'America/Denver' });
        const parts = dateString.split('-');

        const year = parts[0];
        const month = parts[1].padStart(2, '0'); // Ensuring two digits
        const day = parts[2].padStart(2, '0');   // Ensuring two digits

        let confirmChange = true;
        //log the current date and today
        console.log('currentDate:', currentDate);
        console.log('selectedDate:', selectedDate);
        console.log('today:', today);
        console.log('dateString:', dateString);
        // if (currentDate.getFullYear() !== parseInt(year) || currentDate.getMonth() + 1 !== parseInt(month) || currentDate.getDate() + 1 !== parseInt(day)) {
        //     confirmChange = window.confirm("Are you sure you want to edit the scoresheet for a previous date?");
        // }
        // just set to true for now
        confirmChange = true;
        return confirmChange;
    }

    const handleRoundTitleChange = (index, newTitle) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;

      const oldTitle = rounds[index].title;



          setRounds((prevRounds) =>
              prevRounds.map((round, roundIndex) => {
                  if (roundIndex === index) {
                      return {...round, title: newTitle};
                  }
                  return round;
              })
          );


          setScores((prevScores) => {
              const newScores = {...prevScores};
              for (let player in newScores) {
                  if (newScores[player][oldTitle] !== undefined) {
                      newScores[player][newTitle] = newScores[player][oldTitle];
                      if (newTitle !== oldTitle) {
                          delete newScores[player][oldTitle];
                      }
                  }
              }
              return newScores;
          });

          // Adjust the round creator and joker selections (if they are stored in separate state variables)
          setRoundCreators((prevRoundCreators) => {
              const newRoundCreators = {...prevRoundCreators};
              if (newRoundCreators[oldTitle] !== undefined) {
                  newRoundCreators[newTitle] = newRoundCreators[oldTitle];
                  // make sure not to delete the creator if it's the same as the new title
                    if (newTitle !== oldTitle) {
                        delete newRoundCreators[oldTitle];
                    }

              }
              return newRoundCreators;
          });

          setSelectedRounds((prevSelectedRounds) => {
              const newSelectedRounds = {...prevSelectedRounds};
              for (let player in newSelectedRounds) {
                  if (newSelectedRounds[player] === oldTitle) {
                      newSelectedRounds[player] = newTitle;
                  }
              }

              return newSelectedRounds;
          });

      markDirty();
    };

    const focusNewPlayerInput = () => {
      if (newPlayerInputRef.current) {
        newPlayerInputRef.current.focus();
      }
    };

    const startJokerRoulette = useCallback((player) => {
      if (!rounds.length) {
        return;
      }

      const roundTitles = rounds.map(round => round.title);
      const finalIndex = pickJokerRouletteIndex(roundTitles);

      if (finalIndex == null) {
        return;
      }

      const sequence = buildJokerRouletteSequence(
        roundTitles,
        finalIndex,
        {
          minDelay: 35,
          maxDelay: 820,
          easingPower: 1.9,
          fastDurationMs: 1500,
          slowdownCycles: 1,
        },
      );

      clearJokerRouletteForPlayer(player);
      setJokerRouletteSpinningPlayers(prevState => ({
        ...prevState,
        [player]: true,
      }));

      let elapsedDelay = 0;
      const timeoutIds = sequence.map(({ title, delay }) => {
        elapsedDelay += delay;
        return window.setTimeout(() => {
          setJokerRouletteHighlights(prevState => ({
            ...prevState,
            [player]: title,
          }));
        }, elapsedDelay);
      });

      const finalTitle = roundTitles[finalIndex];
      timeoutIds.push(window.setTimeout(() => {
        setSelectedRounds(prevState => ({
          ...prevState,
          [player]: finalTitle,
        }));
        clearJokerRouletteForPlayer(player);
        markDirty();
      }, elapsedDelay + 240));

      jokerRouletteTimeoutsRef.current[player] = timeoutIds;
    }, [clearJokerRouletteForPlayer, markDirty, rounds]);

    const handleJokerSelectionChange = useCallback((player, nextValue) => {
      if (!confirmPastChange()) return;

      if (nextValue === JOKER_RANDOMIZE_VALUE) {
        startJokerRoulette(player);
        return;
      }

      clearJokerRouletteForPlayer(player);
      setSelectedRounds(prevState => ({
        ...prevState,
        [player]: nextValue,
      }));
      markDirty();
    }, [clearJokerRouletteForPlayer, markDirty, startJokerRoulette]);

    const handleAddPlayer = () => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;

      const trimmedName = newPlayerName.trim();
      if (trimmedName) {
        const formattedName = getScoreFieldForName(trimmedName);
        if (!players.includes(formattedName)) {
          setPlayers([...players, formattedName]);
          setNewPlayerName('');
          window.requestAnimationFrame(focusNewPlayerInput);
          markDirty();
        } else {
          alert('Player name already exists!');
          window.requestAnimationFrame(focusNewPlayerInput);
        }
      } else {
        window.requestAnimationFrame(focusNewPlayerInput);
      }
    };

    const transformName = (name) => {
      if (name === 'Dad') {
        return 'Dan';
      } else if (name === 'Mom') {
        return 'Debi';
      } else {
        return name;
      }
    };

    const handleMajorCategoryChange = (roundTitle, newValue) => {
      setSelectedMajorCategories(prevState => ({
        ...prevState,
        [roundTitle]: newValue,
      }));
      markDirty();
    };

    const handleMinor1CategoryChange = (roundTitle, newValue) => {
        setSelectedMinor1Categories(prevState => ({
            ...prevState,
            [roundTitle]: newValue,
        }));
      markDirty();
    };

    const handleMinor2CategoryChange = (roundTitle, newValue) => {
        setSelectedMinor2Categories(prevState => ({
            ...prevState,
            [roundTitle]: newValue,
        }));
      markDirty();
    };

    const handleLinkChange = (index, newLink) => {
        // const confirmChange = confirmPastChange()
        // if (!confirmChange) return;
          setRounds((prevRounds) =>
              prevRounds.map((round, roundIndex) => {
                  if (roundIndex === index) {
                      return {...round, link: newLink};
                  }
                  return round;
              })
          );
        markDirty();
    }

    const handleCooperativeChange = (roundTitle, isChecked) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;
      setCooperativeStatus(prevState => ({
        ...prevState,
        [roundTitle]: isChecked,
      }));
      markDirty();
    };

    const handleReplayChange = (roundTitle, isChecked) => {
        setIsReplay(prevState => ({
            ...prevState,
            [roundTitle]: isChecked,
        }));
      markDirty();
    };

    useEffect(() => {
        console.log('roundCreators changed', roundCreators);
      }, [roundCreators]);

    useEffect(() => {
        console.log('rounds changed', rounds);
      }, [rounds]);

    useEffect(() => {
      const handleCrownWinner = () => {
        const nextWinnerField =
          getPlayerFieldForName(players, tiebreakWinner) || sortedPlayersForDisplay[0] || null;

        if (!nextWinnerField) {
          return;
        }

        const nextWinnerName = getDisplayNameForPlayer(nextWinnerField);

        if (nextWinnerName !== crownedWinner) {
          setCrownedWinner(nextWinnerName);
          markDirty();
        }
      };

      window.addEventListener('scoresheet:crown-winner', handleCrownWinner);

      return () => {
        window.removeEventListener('scoresheet:crown-winner', handleCrownWinner);
      };
    }, [crownedWinner, markDirty, players, sortedPlayersForDisplay, tiebreakWinner]);

    useEffect(() => {
      return () => {
        Object.values(jokerRouletteTimeoutsRef.current).forEach(timeoutIds => {
          timeoutIds.forEach(timeoutId => {
            window.clearTimeout(timeoutId);
          });
        });
        jokerRouletteTimeoutsRef.current = {};
      };
    }, []);

    useEffect(() => {
      if (!openDatePicker) {
        return undefined;
      }

      const handleDatePickerClickAway = (event) => {
        const target = event.target;
        if (!(target instanceof Node)) {
          return;
        }

        if (datePickerFieldRef.current?.contains(target)) {
          return;
        }

        if (target.closest('.MuiPickersPopper-root, .MuiDialog-root')) {
          return;
        }

        setOpenDatePicker(false);
      };

      document.addEventListener('mousedown', handleDatePickerClickAway, true);
      document.addEventListener('touchstart', handleDatePickerClickAway, true);

      return () => {
        document.removeEventListener('mousedown', handleDatePickerClickAway, true);
        document.removeEventListener('touchstart', handleDatePickerClickAway, true);
      };
    }, [openDatePicker]);

    const handleMaxScoreChange = (roundTitle, newMaxScore) => {
                setMaxScores(prevScores => ({
            ...prevScores,
            [roundTitle]: newMaxScore
        }));
        markDirty();
    };

    const setStylePointAnchor = useCallback((playerField, node) => {
      if (node) {
        stylePointAnchorRefs.current[playerField] = node;
        return;
      }

      delete stylePointAnchorRefs.current[playerField];
    }, []);

    const triggerStylePointBurst = useCallback((playerField) => {
      const anchorNode = stylePointAnchorRefs.current[playerField];
      if (!anchorNode) {
        return;
      }

      const rect = anchorNode.getBoundingClientRect();
      window.dispatchEvent(new CustomEvent('scoresheet:burst-stars', {
        detail: {
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
        },
      }));
    }, []);

    const openStylePointDialog = useCallback(() => {
      const defaultRecipient = sortedPlayersForDisplay[0] || players[0] || '';
      if (!defaultRecipient) {
        return;
      }

      setSelectedStylePointPlayer(currentSelection => (
        currentSelection && players.includes(currentSelection) ? currentSelection : defaultRecipient
      ));
      setIsStylePointDialogOpen(true);
    }, [players, sortedPlayersForDisplay]);

    const openTiebreakDialog = useCallback(() => {
      const defaultRecipient =
        getScoreFieldForName(tiebreakWinner) ||
        sortedPlayersForDisplay[0] ||
        players[0] ||
        '';

      if (!defaultRecipient) {
        return;
      }

      setSelectedTiebreakPlayer(currentSelection => (
        currentSelection && players.includes(currentSelection) ? currentSelection : defaultRecipient
      ));
      setIsTiebreakDialogOpen(true);
    }, [players, sortedPlayersForDisplay, tiebreakWinner]);

    const handleAwardStylePoint = () => {
      if (!selectedStylePointPlayer) {
        return;
      }

      const awardedPlayerField = selectedStylePointPlayer;
      setStylePoints(prevStylePoints => (
        incrementStylePoint(prevStylePoints, awardedPlayerField)
      ));
      setIsStylePointDialogOpen(false);
      markDirty();
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          triggerStylePointBurst(awardedPlayerField);
        });
      });
    };

    const handleSetTiebreakWinner = () => {
      const displayName = getDisplayNameForPlayerField(selectedTiebreakPlayer);
      setTiebreakWinner(displayName);
      setIsTiebreakDialogOpen(false);
      markDirty();
    };

    useEffect(() => {
        if (!isSaved) {
            console.log('scoresheet changed, saving...');
            saveData();
        }
    }, [isSaved, saveRequestCount]);

    const buildCurrentSavePayload = useCallback(() => {
        const currentState = latestStateRef.current;
        if (!currentState) {
            return null;
        }

        const patch = buildScoresheetPatch({
            ...currentState,
            serverRoundSnapshot: serverRoundSnapshotRef.current,
            serverPresentationSnapshot: serverPresentationSnapshotRef.current,
        });

        if (!hasScoresheetChanges(patch)) {
            return null;
        }

        return {
            patch,
            payload: {
                ...patch,
                client_id: clientIdRef.current,
                mutation_id: createMutationId(),
                presentation_id: currentState.presID || null,
            },
        };
    }, []);


    const handleCreatorChange = (roundTitle, newCreatorName) => {
      setRoundCreators(prevRoundCreators => ({
        ...prevRoundCreators,
        [roundTitle]: newCreatorName,
      }));


      setScores(prevScores => {
        return clearCreatorScoreForRound(prevScores, players, roundTitle, newCreatorName);
      });

      //call setRounds to trigger the useEffect to recompute medians
        setRounds(prevRounds => {
            const newRounds = [...prevRounds];
            const roundIndex = newRounds.findIndex(round => round.title === roundTitle);
            if (roundIndex !== -1) {
                const transformedCreatorName = transformName(newCreatorName);
                const creatorField = getScoreFieldForName(transformedCreatorName);
                newRounds[roundIndex].creator = newCreatorName;
                if (creatorField) {
                    newRounds[roundIndex][creatorField] = null;
                    const currentExtraScores = getRoundExtraScores(newRounds[roundIndex]);
                    if (Object.prototype.hasOwnProperty.call(currentExtraScores, creatorField)) {
                        const nextExtraScores = { ...currentExtraScores };
                        delete nextExtraScores[creatorField];
                        newRounds[roundIndex].extra_scores = nextExtraScores;
                    }
                }
            }
            return newRounds;
        });
      markDirty();
    };

    const saveData = useCallback(() => {
        if (saveInFlightRef.current) {
            saveQueuedRef.current = true;
            return Promise.resolve();
        }

        const saveRequest = buildCurrentSavePayload();
        if (!saveRequest) {
            setIsSaved(true);
            return Promise.resolve();
        }

        const { patch, payload } = saveRequest;

        const mutationId = payload.mutation_id;
        saveInFlightRef.current = true;
        pendingMutationIdsRef.current.add(mutationId);

        return fetch(url + '/save_scores/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken,
              'Authorization': `Token ${localStorage.getItem('token')}`,
            },
            keepalive: true,
            body: JSON.stringify(payload),
        })
        .then(response => {
          if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          console.log('Success:', data);
          serverRoundSnapshotRef.current = applyPatchToRoundSnapshot(
            serverRoundSnapshotRef.current,
            patch.round_updates,
          );
          serverPresentationSnapshotRef.current = applyPatchToPresentationSnapshot(
            serverPresentationSnapshotRef.current,
            patch.presentation_updates,
          );

          if (data.presentation_id !== undefined && data.presentation_id !== null) {
            setPresID(data.presentation_id);
          }

          const remainingPatch = buildScoresheetPatch({
            ...latestStateRef.current,
            serverRoundSnapshot: serverRoundSnapshotRef.current,
            serverPresentationSnapshot: serverPresentationSnapshotRef.current,
          });
          setIsSaved(!hasScoresheetChanges(remainingPatch));
        })
        .catch((error) => {
          pendingMutationIdsRef.current.delete(mutationId);
          setIsSaved(false);
          console.error('Error:', error);
        })
        .finally(() => {
          saveInFlightRef.current = false;
          if (saveQueuedRef.current) {
            saveQueuedRef.current = false;
            saveData();
          }
        });
    }, [buildCurrentSavePayload, csrfToken, url]);

    useEffect(() => {
      const flushPendingSave = () => {
        const saveRequest = buildCurrentSavePayload();
        if (!saveRequest) {
          return;
        }

        const body = JSON.stringify(saveRequest.payload);
        if (navigator.sendBeacon) {
          navigator.sendBeacon(
            `${url}/save_scores/`,
            new Blob([body], { type: 'application/json' }),
          );
          return;
        }

        fetch(`${url}/save_scores/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body,
          keepalive: true,
        }).catch(() => {});
      };

      window.addEventListener('pagehide', flushPendingSave);

      return () => {
        window.removeEventListener('pagehide', flushPendingSave);
      };
    }, [buildCurrentSavePayload, url]);

    const formatRoundData = (round, index) => {
      let formattedData = {
        creator: roundCreators[round.title] || '',
        title: round.title || '',
        major_category: selectedMajorCategories[round.title] || '',
        minor_category1: selectedMinor1Categories[round.title] || '',
        minor_category2: selectedMinor2Categories[round.title] || '',
        date: round.date || new Date(),
        round_number: index + 1,
        max_score: maxScores[round.title] || 10,
        replay: isReplay[round.title] || false,
        cooperative: cooperativeStatus[round.title] || false,
        notes: round.notes || '', // You can update this field as necessary
        link: round.link || '',  // You can update this field as necessary
        id: round.id || 0,
      };
        Object.keys(scores).forEach((key) => {
            if(key.startsWith('score_')) {
                // as long as scores[key][round.title] is not null, add it to the formattedData object
              formattedData[key] = scores[key][round.title] || null;
              if (scores[key][round.title] === 0)
                formattedData[key] = 0;
            }
        });

    return formattedData;
    };

    const handleAddColumn = (date, number) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;
        const mutationId = createMutationId();
        pendingMutationIdsRef.current.add(mutationId);

        fetch(url + `/create_round/${date}/${number}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'Authorization': `Token ${localStorage.getItem('token')}`,
            },
            body: JSON.stringify({
                client_id: clientIdRef.current,
                mutation_id: mutationId,
            }),
        })
        .then(response => response.json())
        .then(data => {
            console.log('New Round Created:', data);
            setRounds(prevRounds => [...prevRounds, data]);
            setTempTitles(prevTitles => [...prevTitles, data.title]);
            setTempLinks(prevLinks => [...prevLinks, data.link]);
            serverRoundSnapshotRef.current = {
              ...serverRoundSnapshotRef.current,
              [data.id]: makeRoundSnapshot(data),
            };
            markDirty();
        })
        .catch((error) => {
            pendingMutationIdsRef.current.delete(mutationId);
            console.error('Error:', error);
        });
    }

    const handleTempTitleChange = (index, newTitle) => {
        setTempTitles(prevTitles => {
            const newTitles = [...prevTitles];
            newTitles[index] = newTitle;
            return newTitles;
        });
    }

    const handleTempLinkChange = (index, newLink) => {
        setTempLinks(prevLinks => {
            const newLinks = [...prevLinks];
            newLinks[index] = newLink;
            return newLinks;
        });
    }

    const handleRemoveColumn = (roundId) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;
        const confirmDelete = window.confirm("Are you sure you want to delete this round? This action cannot be undone.");
        if (!confirmDelete) return;
        const mutationId = createMutationId();
        pendingMutationIdsRef.current.add(mutationId);

        fetch(url + `/delete_round/${roundId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': csrfToken,
              'Authorization': `Token ${localStorage.getItem('token')}`,
            },
            body: JSON.stringify({
                client_id: clientIdRef.current,
                mutation_id: mutationId,
            }),
        })
        .then(response => {
            if (response.ok) {
                console.log('Round deleted successfully.');
                // Here, update your state or re-fetch data to reflect the round removal.
            } else {
                throw new Error('Failed to delete round.');
            }
        })
        .then(data => {
            console.log('Success:', data);
            setRounds(prevRounds => prevRounds.filter(round => round.id !== roundId));
            // get the index of the round to remove
            const index = rounds.findIndex(round => round.id === roundId);
            // remove the title from tempTitles at the same index
            setTempTitles(prevTitles => prevTitles.filter((title, titleIndex) => titleIndex !== index));
            setTempLinks(prevLinks => prevLinks.filter((link, linkIndex) => linkIndex !== index));
            const nextRoundSnapshot = { ...serverRoundSnapshotRef.current };
            delete nextRoundSnapshot[roundId];
            serverRoundSnapshotRef.current = nextRoundSnapshot;
            markDirty();
        })
        .catch((error) => {
          pendingMutationIdsRef.current.delete(mutationId);
          console.error('Error:', error);
        });
    };



  return (
    <>
    <GlobalStyle />
    <StyledTableContainer>
      <Grid container alignItems="center" spacing={1}>

        {/* Left Section */}
        <Grid item xs={12} md={4}>
          <Box
          display="flex"
          alignItems="center"
          justifyContent={isSmallScreen ? 'center' : 'flex-start'}
          flexDirection={isSmallScreen ? 'column' : 'row'}
          flexWrap="wrap"
          gap={isSmallScreen ? 1 : 0}
          padding={isSmallScreen ? '0.4rem' : '0.2rem'}
          marginLeft={isSmallScreen ? '0' : '0.2rem'}>
            {/*<StyledFormControl>*/}
            {/*  <Select*/}
            {/*    value={selectedDate}*/}
            {/*    onChange={(event) => handleChangeDate(event)}*/}
            {/*  >*/}
            {/*    {sortedDates.map((date, index) => (*/}
            {/*      <MenuItem key={index} value={date}>{date}</MenuItem>*/}
            {/*    ))}*/}
            {/*  </Select>*/}
            {/*    <StyledButton variant="contained" color="secondary" onClick={() => handleChangeDate()}>*/}
            {/*        Today*/}
            {/*    </StyledButton>*/}
            {/*</StyledFormControl>*/}

            <StyledFormControl>
                <LocalizationProvider dateAdapter={AdapterDayjs}>
                    <DatePicker
                    open={openDatePicker}
                    value={selectedDate ? dayjs(selectedDate) : null}
                      onChange={(newValue) => {
                        if (!newValue) {
                          return;
                        }
                        const formattedDate = dayjs(newValue).format('YYYY-MM-DD');
                        handleChangeDate(formattedDate);
                        setOpenDatePicker(false); // Close the DatePicker after selection
                      }}
                    onClose={() => setOpenDatePicker(false)}
                      // renderInput={(params) => (
                      //   <TextField
                      //     {...params}
                      //     InputProps={{
                      //       ...params.InputProps,
                      //       style: { backgroundColor: '#333' } // Apply background color directly
                      //     }}
                      //   />
                      // )}
                    slots={{
                        day: CustomDay,
                    }}
                    slotProps={{
                      textField: {
                        ref: datePickerFieldRef,
                        onClick: () => setOpenDatePicker(true),
                        placeholder: 'Select date',
                        inputProps: {
                          readOnly: true,
                          style: {
                            cursor: 'pointer',
                          },
                        },
                        sx: {
                          minWidth: isSmallScreen ? '100%' : '9.5rem',
                          maxWidth: isSmallScreen ? '18rem' : '10.25rem',
                          margin: '0.4rem',
                          '& .MuiInputBase-root': {
                            backgroundColor: '#333',
                            color: '#fff',
                            fontFamily: 'Monaco',
                            borderRadius: 0,
                            cursor: 'pointer',
                          },
                          '& .MuiInputAdornment-root': {
                            marginLeft: 0,
                            marginRight: '0.2rem',
                          },
                          '& .MuiIconButton-root': {
                            color: '#fff',
                            padding: '4px',
                          },
                          '& .MuiOutlinedInput-notchedOutline': {
                            border: 'none',
                          },
                          '& input': {
                            color: '#fff',
                            fontFamily: 'Monaco',
                            textAlign: 'center',
                            padding: '8px 8px 8px 12px',
                            cursor: 'pointer',
                          },
                        },
                      },
                      day: {
                        sortedDates,
                      },
                    }}
                    />
                </LocalizationProvider>
            </StyledFormControl>


            <StyledTextField
              inputRef={newPlayerInputRef}
              value={newPlayerName}
              onChange={(e) => setNewPlayerName(e.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  handleAddPlayer();
                }
              }}
              variant="outlined"
              placeholder="Add player"
              style={{
                margin: "0.4rem",
                marginLeft: isSmallScreen ? "0.4rem" : "1rem",
                width: isSmallScreen ? '100%' : undefined,
                maxWidth: isSmallScreen ? '18rem' : undefined,
              }}
            />

            <StyledButton variant="contained" color="secondary" onClick={handleAddPlayer}>
              Add
            </StyledButton>
              <StyledFormControl>
                <StyledInputLabel className={"showonsmall"}>Round</StyledInputLabel>
                  <StyledSelect
                    className={"showonsmall"}
                    value={selectedColumnIndex.toString()}
                    MenuProps={dropdownMenuProps}
                    onChange={e => {
                        const value = parseInt(e.target.value, 10);
                        setSelectedColumnIndex(value);
                    }}
                >
                    <MenuItem value={1}>Joker</MenuItem>
                    {rounds.map((round, index) => (
                        <MenuItem key={index} value={index+2}>{round.title}</MenuItem>
                    ))}
                </StyledSelect>
              </StyledFormControl>
          </Box>
        </Grid>

        {/* Right Section */}
        <Grid item xs={12} md={8}>
          <Box
            display="flex"
            justifyContent={isSmallScreen ? 'center' : 'flex-end'}
            alignItems="center"
            flexDirection={isSmallScreen ? 'column' : 'row'}
            flexWrap="wrap"
            gap={isSmallScreen ? 1 : 0}
          >
            <StyledButton variant="contained" color="secondary" onClick={() => setIsBottomRowVisible(prevState => !prevState)}>
              Toggle Details
            </StyledButton>
            <StyledButton variant="contained" color="secondary" onClick={() => handleAddColumn(selectedDate, rounds.length + 1)}>
              Add Round
            </StyledButton>

            <StyledButton variant="contained" color="primary" onClick={saveData} style={{ backgroundColor: isSaved ? '#1e7662' : '#810e19' }}>
              Save Scoresheet
            </StyledButton>

            {/*<StyledButton*/}
            {/*    variant="outlined"*/}
            {/*    color="primary"*/}
            {/*    onClick={() => setShowPic(true)}*/}
            {/*  >*/}
            {/*    Show Picture*/}
            {/*</StyledButton>*/}
            {/*<StyledButton variant="outlined" onClick={pulsePlayer}>*/}
            {/*    Pulse “Player”*/}
            {/*</StyledButton>*/}
          </Box>
        </Grid>

                {/* Animated image appears here once showPic is true */}
      {showPic && (
          <Box
            mt={2}
            textAlign="center"
            /* Box = the fixed-size frame */
            display="inline-block"
            width={240}
            height={240}
            position="relative"
            overflow="hidden"   // keeps scaled edges from spilling out
            borderRadius={2}
          >
            <motion.img
              src="https://picsum.photos/240"
              alt="Surprise!"
              /* pop-in once, then gentle pulse forever */
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{
                opacity: 1,
                scale: [1, 1.1, 1],          // breathe 100 % → 110 % → 100 %
              }}
              transition={{
                duration: 0.4,               // fade-in
                scale: {
                  duration: 3,               // one “breath”
                  repeat: Infinity,
                  repeatType: "mirror",
                  ease: "easeInOut",
                },
              }}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",          // fill the frame without stretching
                borderRadius: 8,
              }}
            />
          </Box>
        )}


      </Grid>
      <StyledTable id="table">
        <TableHead>
          <TableRow>
            <StyledTableCell><div className={"textCell"}>
                <motion.div
                    className="textCell"
                    animate={playerControls}       // see step 3
                    initial={false}                // don’t animate on first render
                >
                    Player
                </motion.div>
            </div></StyledTableCell>
            <StyledTableCell className={selectedColumnIndex === 1 ? 'selected-column' : ''}><div className={"textCell"}>Joker</div></StyledTableCell>
            {rounds.map((round, index) => (
              <StyledTableCell key={index} className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>
                <StyledTextField
                    value={tempTitles[index]} // set the default value to round.title
                    onChange={(e) => {handleTempTitleChange(index, e.target.value)}} // update the temp title on change
                    onBlur={(e) => {
                        handleRoundTitleChange(index, e.target.value); // update the global state on blur
                    }}
                    fullWidth
                    multiline
                    rowsMax={3}
                    // use getFontSIze to set the font size based on the length of the title
                    inputProps={{ style: { fontSize: getFontSize(round.title) } }}
                />
            </StyledTableCell>
            ))}
            <StyledTableCell sx={{color:'white'}}><div>Joker Bonus</div></StyledTableCell>
            <StyledTableCell sx={{color:'white'}}><div>Creator Bonus</div></StyledTableCell>
              <StyledTableCell sx={{color:'white'}} onClick={() => setIsSortAscending(!isSortAscending)}><div>Total</div></StyledTableCell>
                     <StyledTableCell sx={{color:'white', marginX:"0px", padding:"0"}}><div></div></StyledTableCell>

          </TableRow>
        </TableHead>
        <TableBody>
          {sortedPlayersForDisplay.map((player) => {
              const stylePointTheme = getStylePointTheme(stylePoints, player);
              const activeJokerRouletteTitle = jokerRouletteHighlights[player];
              const isJokerRouletteSpinning = Boolean(jokerRouletteSpinningPlayers[player]);
              return (<TableRow key={player}>
                  <StyledTableCell player={player}>
                      <PlayerNameStack>
                          <PlayerNameAnchor>
                              {crownedPlayer === player && (
                                  <WinnerCrown
                                      initial={{ opacity: 0, y: -5, rotate: 6, scale: 0.8 }}
                                      animate={{ opacity: 1, y: 0, rotate: 22, scale: 1 }}
                                      transition={{ duration: 0.35, ease: 'easeOut' }}
                                  >
                                      <CrownIcon streak={crownStreak} />
                                  </WinnerCrown>
                              )}
                              {hasStylePointAward(stylePoints, player) && (
                                  <StylePointShades
                                      ref={(node) => setStylePointAnchor(player, node)}
                                      initial={{ opacity: 0, y: -3, rotate: -30, scale: 0.8 }}
                                      animate={{ opacity: 1, y: 0, rotate: -18, scale: 1 }}
                                      transition={{ duration: 0.28, ease: 'easeOut' }}
                                  >
                                      <SunglassesIcon theme={stylePointTheme} />
                                  </StylePointShades>
                              )}
                              <a
                                  href={url + `/player_profile/${getDisplayNameForPlayerField(player)}/`}
                                  className="player_name"
                                  data-player={getDisplayNameForPlayerField(player)}
                              >
                                  {getDisplayNameForPlayerField(player)}
                              </a>
                          </PlayerNameAnchor>
                      </PlayerNameStack>
                  </StyledTableCell>
                  <StyledTableCell sx={{maxWidth: '200px'}} className={selectedColumnIndex === 1 ? 'selected-column' : ''}>
                      <StyledFormControl>
                          <InputLabel id="demo-simple-select-label"></InputLabel>
                          <StyledSelect
                              sx={{maxWidth: '150px'}}
                              MenuProps={dropdownMenuProps}
                              labelId="demo-simple-select-label"
                              id="demo-simple-select"
                              displayEmpty
                              value={isJokerRouletteSpinning ? JOKER_RANDOMIZE_VALUE : (selectedRounds[player] || "Select")} // Access the selected round for this player
                              renderValue={(value) => {
                                if (value === JOKER_RANDOMIZE_VALUE) {
                                  return <span style={{ color: '#f6c343', fontWeight: 700 }}>Randomizing...</span>;
                                }
                                if (value === "Select") {
                                  return '- Select -';
                                }
                                return value;
                              }}
                              onChange={(event) => handleJokerSelectionChange(player, event.target.value)}
                          >
                              <MenuItem value={"Select"}>- Select -</MenuItem>
                              {rounds.map((round, index) => (
                                  <MenuItem value={round.title} key={index}>{round.title}</MenuItem>
                              ))}
                              <MenuItem
                                  value={JOKER_RANDOMIZE_VALUE}
                                  sx={{ color: '#f6c343 !important', fontWeight: 700 }}
                              >
                                  Randomize
                              </MenuItem>
                          </StyledSelect>
                      </StyledFormControl>
                  </StyledTableCell>
                  {rounds.map((round, index) => (
                      <StyledTableCell
                           sx={{color:textColor}}
                           className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}
                          key={index}
                          contentEditable
                          style={{
                              backgroundColor:
                                  activeJokerRouletteTitle === round.title
                                      ? '#f3bc34'
                                      : (!isJokerRouletteSpinning && selectedRounds[player] === round.title)
                                      ? '#1e7662'
                                      : roundCreators[round.title] === getDisplayNameForPlayerField(player)
                                          ? '#810e19'
                                          : '#333',
                              color: 'white',
                              fontFamily: 'Monaco',
                                fontSize: "1rem",
                          }}
                          onBlur={(event) => handleScoreChange(event, player, round.title, round)}
                      >
                          {getDisplayedRoundScore(scores, player, round)}
                      </StyledTableCell>
                  ))}
                  <StyledTableCell>
                  <div className={"textCell"}>
                    {getDisplayedJokerBonus(rounds, scores, player, selectedRounds[player])}
                  </div>
                </StyledTableCell>
                  <StyledTableCell><div className={"textCell"}>
                    {getDisplayedCreatorBonus(rounds, player, selectedRounds[player], medianScores)}
                  </div></StyledTableCell>

                  <StyledTableCell>
                      <div className={"textCell"}>
                        {getDisplayedFinalTotal(rounds, scores, player, selectedRounds[player], medianScores)}
                      </div>
                    </StyledTableCell>
                      <StyledTableCell>
                          <XButton player={player} onClick={() => handleRemovePlayer(player)}>X</XButton>
                      </StyledTableCell>
            </TableRow>

            )
          })}

          <StyledTableRow>
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
              {rounds.map((round, index) => (
                  <StyledTableCell key={index} className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>
                    <StyledFormControlLabel
                      control={
                        <Checkbox
                          style={{transform: 'scale(1.5)'}}
                          checked={cooperativeStatus[round.title] || false}
                          onChange={(event) => handleCooperativeChange(round.title, event.target.checked)}
                        />
                      }
                      label="Coop"
                    />
                    </StyledTableCell>
                    ))}

            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}

          </StyledTableRow>
        {isBottomRowVisible && (
        <StyledTableRow>
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            {rounds.map((round, index) => (
              <StyledTableCell key={index} className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>
                {/* Checkbox to indicate if the round is cooperative */}

              <StyledFormControlLabel
                  control={
                    <Checkbox
                      checked={isReplay[round.title] || false}
                      onChange={(event) => handleReplayChange(round.title, event.target.checked)}
                    />
                  }
                  label="Replay"
                />
              </StyledTableCell>
            ))}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
        </StyledTableRow>
        )}
        {isBottomRowVisible && (
        <StyledTableRow>
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
                {rounds.map((round, index) => (
                    <StyledTableCell key={index} className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>

                              <StyledFormControlLabel
                                    control={
                                  <Input
                                      value = {maxScores[round.title] || 10}
                                        onChange={(e) => handleMaxScoreChange(round.title, parseFloat(e.target.value))}
                                        inputProps={{
                                            step: 0.5,
                                            min: 1,
                                            max: 100,
                                            type: 'number',
                                            'aria-labelledby': 'input-slider'
                                        }}
                                    />
                                }
                            label="Max Score"
                                    // put the label to the left of the input
                                  // and can we add some spacing between the label and the input?
                                  labelPlacement="top"
                                    // make the label smaller
                                    sx={{fontSize: '0.6rem'}}
                            />
                        </StyledTableCell>
                ))}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
        </StyledTableRow>
        )}
        {isBottomRowVisible && (
        <StyledTableRow>
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            {rounds.map((round, index) => (
                <StyledTableCell className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>
                  <StyledFormControlLabel
                        label="Creator"
                        labelPlacement="top"
                        control={
                      <Select
                          value = {roundCreators[round.title] || ''}
                            onChange={(e) => handleCreatorChange(round.title, e.target.value)}
                        >
                            <MenuItem value="">Unknown</MenuItem> {/* Added "None" option */}
                            {creatorOptions.map((player, index) => (
                                <MenuItem key={index} value={player}>
                                    {player}
                                </MenuItem>
                            ))}
                        </Select>
                    }
                />
                </StyledTableCell>
            ))}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
        </StyledTableRow>
        )}
        {isBottomRowVisible && (
        <StyledTableRow>
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            {rounds.map((round, index) => (
                <StyledTableCell className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>
                  <StyledFormControlLabel
                      label="Category"
                        labelPlacement="top"
                      // make the label smaller
                        sx={{fontSize: '0.6rem'}}
                        control={
                      <Select
                            value = {selectedMajorCategories[round.title] || ''}
                            onChange={(e) => handleMajorCategoryChange(round.title, e.target.value)}
                        >
                            {majorCategories.sort((a, b) => a.localeCompare(b)).map((category, index) => (
                                <MenuItem key={index} value={category}>
                                    {category}
                                </MenuItem>
                            ))}
                        </Select>
                    }
                />
                </StyledTableCell>
            ))}

            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
        </StyledTableRow>
        )}
        {isBottomRowVisible && (
        <StyledTableRow>
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            {rounds.map((round, index) => (
                <StyledTableCell  className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>
                  <StyledFormControlLabel
                      label="Sub1"
                        labelPlacement="top"
                        control={
                      <Select
                            value = {selectedMinor1Categories[round.title] || ''}
                            onChange={(e) => handleMinor1CategoryChange(round.title, e.target.value)}
                        >
                            {minor1Categories.sort((a, b) => a.localeCompare(b)).map((category, index) => (
                                <MenuItem key={index} value={category}>
                                    {category}
                                </MenuItem>
                            ))}
                        </Select>
                    }
                />
                </StyledTableCell>
            ))}

            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
        </StyledTableRow>
        )}
        {isBottomRowVisible && (
        <StyledTableRow>
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            {rounds.map((round, index) => (
                <StyledTableCell key={index} className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>
                  <StyledFormControlLabel
                      label="Sub2"
                        labelPlacement="top"
                      // make the label smaller
                        control={
                      <Select
                            value = {selectedMinor2Categories[round.title] || ''}
                            onChange={(e) => handleMinor2CategoryChange(round.title, e.target.value)}
                        >
                            {minor2Categories.sort((a, b) => a.localeCompare(b)).map((category, index) => (
                                <MenuItem key={index} value={category}>
                                    {category}
                                </MenuItem>
                            ))}
                        </Select>
                    }
                />
                </StyledTableCell>
            ))}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
        </StyledTableRow>
        )}
        {isBottomRowVisible && (
        <StyledTableRow>
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            {rounds.map((round, index) => (
              <StyledTableCell key={index} className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>
                <StyledTextField
                    value={tempLinks[index]} // set the default value to round.title
                    onChange={(e) => {handleTempLinkChange(index, e.target.value)}} // update the temp title on change
                    onBlur={(e) => {
                        handleLinkChange(index, e.target.value); // update the global state on blur
                    }}
                    fullWidth
                    multiline
                    rowsMax={3}
                    // use getFontSIze to set the font size based on the length of the title
                    inputProps={{ style: { fontSize: getFontSize(round.link) } }}
                />
            </StyledTableCell>
            ))}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
        </StyledTableRow>
        )}
        {isBottomRowVisible && (
        <StyledTableRow>
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            {rounds.map((round, index) => (
                <StyledTableCell key={index} className={index + 2 === selectedColumnIndex ? 'selected-column' : ''}>
                    <StyledButton variant="contained" color="secondary" onClick={() => handleRemoveColumn(round.id)}>
                        Delete
                    </StyledButton>
                </StyledTableCell>
            ))}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
          </StyledTableRow>
        )}
        {isBottomRowVisible && (
          <StyledTableRow>
            <TableCell colSpan={2}>
              <div className="textCell"><strong>Night Roles</strong></div>
            </TableCell>
            <TableCell colSpan={rounds.length + 4}>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(180px, 220px))', gap: '10px', justifyContent: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ color: '#fff', fontFamily: 'Monaco', fontSize: '0.85rem' }}>Host</span>
                  <MetadataFormControl>
                    <StyledSelect
                      displayEmpty
                      value={host}
                      onChange={(e) => {
                        setHost(e.target.value);
                        markDirty();
                      }}
                    >
                      <MenuItem value="">—</MenuItem>
                      {playerNamesDisplay.map((name) => (
                        <MenuItem key={name} value={name}>{name}</MenuItem>
                      ))}
                    </StyledSelect>
                  </MetadataFormControl>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ color: '#fff', fontFamily: 'Monaco', fontSize: '0.85rem' }}>Scorekeeper</span>
                  <MetadataFormControl>
                    <StyledSelect
                      displayEmpty
                      value={scorekeeper}
                      onChange={(e) => {
                        setScorekeeper(e.target.value);
                        markDirty();
                      }}
                    >
                      <MenuItem value="">—</MenuItem>
                      {playerNamesDisplay.map((name) => (
                        <MenuItem key={name} value={name}>{name}</MenuItem>
                      ))}
                    </StyledSelect>
                  </MetadataFormControl>
                </div>
              </div>
            </TableCell>
          </StyledTableRow>
        )}
        {isBottomRowVisible && (
          <StyledTableRow>
            <TableCell colSpan={2}>
              <div className="textCell"><strong>Style points</strong></div>
            </TableCell>
            <TableCell colSpan={rounds.length + 4}>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(160px, 1fr))', gap: '8px' }}>
                {playerNamesDisplay.map(name => (
                  <label key={name} style={{ display:'flex', alignItems:'center', gap:8 }}>
                    <span style={{ minWidth:80 }}>{name}</span>
                    <Input
                      value={stylePoints?.[name] ?? ''}
                      onChange={(e)=>{
                        setStylePoints(prev => setStylePointValue(prev, name, e.target.value));
                        markDirty();
                      }}
                      inputProps={{ step:0.5, min:0, type:'number' }}
                    />
                  </label>
                ))}
              </div>
            </TableCell>
          </StyledTableRow>
        )}
        </TableBody>
      </StyledTable>
      <MetadataSection>
        <MetadataGrid>
          <MetadataActionField>
            <MetadataActionRow>
              <MetadataActionButtons>
                <MetadataActionPrimaryButton type="button" onClick={openTiebreakDialog}>
                  {tiebreakWinner ? `Tiebreak: ${tiebreakWinner}` : 'Set Tiebreak Winner'}
                </MetadataActionPrimaryButton>
                <StyledButton type="button" onClick={() => window.dispatchEvent(new Event('scoresheet:crown-winner'))}>
                  Crown Winner
                </StyledButton>
                <StyledButton type="button" onClick={openStylePointDialog}>
                  Award Style Point
                </StyledButton>
              </MetadataActionButtons>
            </MetadataActionRow>
          </MetadataActionField>

          <MetadataNotesFieldWrapper>
            <MetadataNotesField
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
                markDirty();
              }}
              multiline
              rows={isSmallScreen ? 2 : 1}
              placeholder="Enter Nightly Notes"
            />
          </MetadataNotesFieldWrapper>
        </MetadataGrid>
      </MetadataSection>
      <Dialog
        open={isStylePointDialogOpen}
        onClose={() => setIsStylePointDialogOpen(false)}
        fullWidth
        maxWidth="xs"
        PaperProps={{
          sx: {
            backgroundColor: '#333',
            color: '#fff',
            borderRadius: 0,
            border: '1px solid #1e7662',
            boxShadow: '0 16px 36px rgba(0, 0, 0, 0.45)',
          },
        }}
      >
        <DialogTitle sx={{ fontFamily: 'Monaco, monospace', color: '#fff' }}>Award Style Point</DialogTitle>
        <DialogContent sx={{ color: '#fff' }}>
          <Box sx={{ pt: 1 }}>
            <FormControl
              fullWidth
              sx={{
                '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.72)', fontFamily: 'Monaco, monospace' },
                '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                '& .MuiOutlinedInput-root': {
                  backgroundColor: '#333',
                  color: '#fff',
                  fontFamily: 'Monaco, monospace',
                },
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#1e7662',
                },
                '& .MuiSvgIcon-root': { color: '#fff' },
              }}
            >
              <InputLabel id="style-point-player-label">Player</InputLabel>
              <Select
                labelId="style-point-player-label"
                value={selectedStylePointPlayer}
                label="Player"
                onChange={(event) => setSelectedStylePointPlayer(event.target.value)}
                MenuProps={{
                  PaperProps: {
                    sx: {
                      backgroundColor: '#333',
                      color: '#fff',
                      border: '1px solid #1e7662',
                      '& .MuiMenuItem-root': {
                        fontFamily: 'Monaco, monospace',
                      },
                      '& .MuiMenuItem-root.Mui-selected': {
                        backgroundColor: '#1e7662',
                      },
                      '& .MuiMenuItem-root:hover': {
                        backgroundColor: '#185e4f',
                      },
                    },
                  },
                }}
              >
                {sortedPlayersForDisplay.map((playerField) => (
                  <MenuItem key={playerField} value={playerField}>
                    {getDisplayNameForPlayerField(playerField)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <StyledButton type="button" onClick={() => setIsStylePointDialogOpen(false)}>
            Cancel
          </StyledButton>
          <StyledButton type="button" onClick={handleAwardStylePoint}>
            Award
          </StyledButton>
        </DialogActions>
      </Dialog>
      <Dialog
        open={isTiebreakDialogOpen}
        onClose={() => setIsTiebreakDialogOpen(false)}
        fullWidth
        maxWidth="xs"
        PaperProps={{
          sx: {
            backgroundColor: '#333',
            color: '#fff',
            borderRadius: 0,
            border: '1px solid #1e7662',
            boxShadow: '0 16px 36px rgba(0, 0, 0, 0.45)',
          },
        }}
      >
        <DialogTitle sx={{ fontFamily: 'Monaco, monospace', color: '#fff' }}>Set Tiebreak Winner</DialogTitle>
        <DialogContent sx={{ color: '#fff' }}>
          <Box sx={{ pt: 1 }}>
            <FormControl
              fullWidth
              sx={{
                '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.72)', fontFamily: 'Monaco, monospace' },
                '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                '& .MuiOutlinedInput-root': {
                  backgroundColor: '#333',
                  color: '#fff',
                  fontFamily: 'Monaco, monospace',
                },
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#1e7662',
                },
                '& .MuiSvgIcon-root': { color: '#fff' },
              }}
            >
              <InputLabel id="tiebreak-player-label">Player</InputLabel>
              <Select
                labelId="tiebreak-player-label"
                value={selectedTiebreakPlayer}
                label="Player"
                onChange={(event) => setSelectedTiebreakPlayer(event.target.value)}
                MenuProps={{
                  PaperProps: {
                    sx: {
                      backgroundColor: '#333',
                      color: '#fff',
                      border: '1px solid #1e7662',
                      '& .MuiMenuItem-root': {
                        fontFamily: 'Monaco, monospace',
                      },
                      '& .MuiMenuItem-root.Mui-selected': {
                        backgroundColor: '#1e7662',
                      },
                      '& .MuiMenuItem-root:hover': {
                        backgroundColor: '#185e4f',
                      },
                    },
                  },
                }}
              >
                <MenuItem value="">— None —</MenuItem>
                {sortedPlayersForDisplay.map((playerField) => (
                  <MenuItem key={playerField} value={playerField}>
                    {getDisplayNameForPlayerField(playerField)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <StyledButton type="button" onClick={() => setIsTiebreakDialogOpen(false)}>
            Cancel
          </StyledButton>
          <StyledButton
            type="button"
            onClick={() => {
              if (!selectedTiebreakPlayer) {
                setTiebreakWinner('');
                setIsTiebreakDialogOpen(false);
                markDirty();
                return;
              }

              handleSetTiebreakWinner();
            }}
          >
            Save
          </StyledButton>
        </DialogActions>
      </Dialog>
    </StyledTableContainer>
    </>
  );
};

// CustomDay component
function CustomDay(props) {

    const { day, outsideCurrentMonth, sortedDates, ...other } = props;
    const dateString = day.format('YYYY-MM-DD');
    // also make sure the date is not outside the current month
    const isSelected = sortedDates.includes(dateString) && !outsideCurrentMonth;

  return (
    <Badge
      key={props.day.toString()}
      overlap="circular"
      badgeContent={isSelected ? '⬤' : undefined}
    >
      <PickersDay {...other} outsideCurrentMonth={outsideCurrentMonth} day={day} />
    </Badge>
  );
}

export default PlayerTable;
