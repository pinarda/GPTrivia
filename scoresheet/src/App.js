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
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Menu,
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
  applyPresentationFieldsForSelectedDate,
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
import { getScoreCellJokerAction } from './scoreCellMenu';
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
  resolveScoresheetDate,
} from './presentationData';
import {
  buildJokerRouletteSequence,
  JOKER_RANDOMIZE_VALUE,
  pickJokerRouletteIndex,
} from './jokerRoulette';
import {
  getPlayerIconUrl,
  readPlayerIconMap,
} from './playerIcons';
import {
  readPlayerColorMap,
} from './playerColors';
import {
    applyCooperativeScoreEntry,
    extractPlayersFromRounds,
    getDisplayNameForPlayerField,
    getMergedRoundScoreMap,
    getRoundExtraScores,
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

    let activePlayerColorMapping = basePlayerColorMapping;

    function resolvePlayerColor(playerField) {
      return getPlayerColor(playerField, activePlayerColorMapping);
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
      background-color: var(--scoresheet-surface, #333);
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
        color: var(--scoresheet-text, #fff);
        text-align: center;
        font-family: Monaco;
        font-size: 1rem;
      }
      a {
        color: var(--scoresheet-text, #fff);
        text-decoration: none;  
        font-family: Monaco;
        font-size: 1rem;
        &:hover {
          color: ${props => resolvePlayerColor(props.player) || '#000'};
        }
      }

      @media (max-width: 1000px) {
        && {
          padding: 0.6rem;
        }

        div,
        .textCell,
        a {
          font-size: 1.05rem;
        }
      }
    `;


    const StyledTableRow = styled(TableRow)({
      borderBottom: '2px solid var(--scoresheet-row-divider, #333)',
    });

    const StyledButton = styled.button.attrs(({ className }) => ({
      className: className ? `star-ricochet ${className}` : 'star-ricochet',
    }))`
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

      @media (max-width: 1000px) {
        padding: 0.48rem 0.84rem;
        margin: 0;
        font-size: 1.05rem;
        min-height: 2.4rem;
        min-width: 7.75rem;
        line-height: 1.2;
      }
  `

    const StyledSelect = styled(Select)`
        &&.MuiInputBase-root,
        &&.MuiOutlinedInput-root {
          background-color: var(--scoresheet-surface, #333);
          color: var(--scoresheet-text, #fff);
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
          color: var(--scoresheet-text, #fff);
          font-size: 0.75rem;
          font-family: "Monaco";
          padding: 0.16rem 1.45rem 0.16rem 0.45rem;
          min-height: unset;
        }

        && .MuiSvgIcon-root {
          color: var(--scoresheet-text, #fff);
          font-size: 1.05rem;
        }

        @media (max-width: 1000px) {
          && .MuiSelect-select {
            font-size: 0.92rem;
            padding: 0.4rem 1.7rem 0.4rem 0.6rem;
          }

          && .MuiSvgIcon-root {
            font-size: 1.15rem;
          }
        }
    `;

    const dropdownMenuProps = {
      PaperProps: {
        sx: {
          backgroundColor: 'var(--scoresheet-menu-bg, #333)',
          color: 'var(--scoresheet-text, #fff)',
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
            backgroundColor: 'var(--scoresheet-menu-hover, #185e4f)',
          },
          '& .MuiMenuItem-root:hover': {
            backgroundColor: 'var(--scoresheet-menu-hover, #185e4f)',
          },
        },
      },
    };

    const StyledFormControl = styled(FormControl)`
        background-color: var(--scoresheet-surface, #333);
        color: var(--scoresheet-text, #fff);
        max-width: 8rem;
        && * {
          color: var(--scoresheet-text, #fff);
          font-family: "Monaco";
          font-size: 0.8rem;
          padding: 0.15rem;
          margin: 0rem;
          //margin: 5px 12px;
        }

        @media (max-width: 1000px) {
          max-width: 11rem;

          && * {
            font-size: 0.92rem;
          }
        }
      `;

    const RoundDateFormControl = styled(StyledFormControl)`
      @media (max-width: 750px) {
        width: min(100%, 21.35rem);
        max-width: min(100%, 21.35rem);
        padding: 0.34rem 0.42rem 0.42rem;
        border: 2px solid var(--scoresheet-border-soft, rgba(255, 255, 255, 0.22));
        box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
        box-sizing: border-box;
      }
    `;

    const RoundSwitchFormControl = styled(StyledFormControl)`
      @media (max-width: 750px) {
        width: min(100%, 21.35rem);
        max-width: min(100%, 21.35rem);
        padding: 0.34rem 0.42rem 0.42rem;
        border: 2px solid var(--scoresheet-border-soft, rgba(255, 255, 255, 0.22));
        box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
        box-sizing: border-box;
      }
    `;

    const RoundNavigationStack = styled.div`
      display: flex;
      flex-direction: column;
      align-items: center;
      width: auto;
      max-width: 100%;
      min-width: 0;
      flex: 0 0 auto;
      gap: 0.45rem;

      @media (max-width: 750px) {
        width: 100%;
      }
    `;

    const RoundNavigationControlGroup = styled.div`
      display: flex;
      align-items: center;
      justify-content: center;
      max-width: 100%;
      min-width: 0;
      gap: 0.4rem;
      flex-wrap: nowrap;

      @media (max-width: 750px) {
        width: 100%;
        flex-direction: column;
        gap: 0.7rem;
      }
    `;

    const JokerFormControl = styled(StyledFormControl).attrs(({ className }) => ({
      className: className ? `star-ricochet ${className}` : 'star-ricochet',
    }))`
      width: 100%;
      min-width: 0;
      max-width: 8rem;

      @media (max-width: 1500px) {
        max-width: 100%;
      }

      @media (max-width: 1000px) {
        max-width: 100%;
      }
    `;

    const JokerSelect = styled(StyledSelect)`
      width: 100%;
      max-width: 100%;
      min-width: 0;

      && .MuiOutlinedInput-root {
        box-shadow: inset 0 0 0 1px #1e7662;
      }

      && .MuiOutlinedInput-notchedOutline {
        border: 2px solid #1e7662 !important;
      }

      &&:hover .MuiOutlinedInput-notchedOutline,
      &&.Mui-focused .MuiOutlinedInput-notchedOutline,
      && .Mui-focused .MuiOutlinedInput-notchedOutline {
        border: 2px solid #2c9d84 !important;
      }

      && .MuiSelect-select {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      @media (max-width: 1500px) {
        && .MuiSelect-select {
          font-size: 0.72rem;
          padding-right: 1.25rem;
        }
      }

      @media (max-width: 1100px) {
        && .MuiSelect-select {
          font-size: 0.68rem;
        }
      }
    `;

    const StyledInputLabel = styled(InputLabel)`
      color: var(--scoresheet-text, #fff);
      text-align: center;
        font-family: Monaco;
        font-size: 0.8rem;

        @media (max-width: 1000px) {
          font-size: 0.92rem;
        }
    `;

    const RoundSwitchHelper = styled.div`
      display: none;

      @media (max-width: 750px) {
        display: block;
        width: min(100%, 21.35rem);
        padding: 0.38rem 0.62rem;
        background-color: var(--scoresheet-surface, #333);
        border: 1px solid var(--scoresheet-border-soft, rgba(255, 255, 255, 0.22));
        box-sizing: border-box;
        color: var(--scoresheet-text-muted, rgba(255, 255, 255, 0.5));
        font-family: "Monaco";
        font-size: 0.72rem;
        line-height: 1.3;
        text-align: center;
      }
    `;

    const RoundSwitchSelect = styled(StyledSelect)`
      @media (max-width: 750px) {
        && .MuiOutlinedInput-notchedOutline {
          border-width: 2px;
          border-color: var(--scoresheet-border-soft, rgba(255, 255, 255, 0.22));
        }

        &&:hover .MuiOutlinedInput-notchedOutline,
        &&.Mui-focused .MuiOutlinedInput-notchedOutline,
        && .Mui-focused .MuiOutlinedInput-notchedOutline {
          border-width: 2px;
          border-color: var(--scoresheet-border-soft, rgba(255, 255, 255, 0.22));
        }

        && .MuiSelect-select {
          font-size: 0.98rem;
          font-weight: 700;
          text-align: center;
        }
      }
    `;




    const StyledFormControlLabel = styled(FormControlLabel)`
        background-color: var(--scoresheet-surface, #333);
        color: var(--scoresheet-text, #fff);
        font-size: 0.8rem;
      && * {
        color: var(--scoresheet-text, #fff);
        font-family: "Monaco";
        font-size: 0.9rem;
      }

      @media (max-width: 1000px) {
        font-size: 0.92rem;

        && * {
          font-size: 0.98rem;
        }
      }
    `;

    const StyledTableContainer = styled(TableContainer)`
        background-color: var(--scoresheet-surface, #333);
        color: var(--scoresheet-text, #fff);
        width: 100%;
      
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
      color: var(--scoresheet-text, #fff);
      // prevent wrapping
      div {
          font-size: 12px;
          font-family: "Monaco";
          color: var(--scoresheet-text, #fff);
          border: none;
          background-color: var(--scoresheet-surface, #333);
          text-align: center;
            white-space: nowrap;
            overflow: hidden;
        }
      
      * {
        font-size: 1rem;
        font-family: "Monaco";
        color: var(--scoresheet-text, #fff);
      }
      
      div > input {
        color: var(--scoresheet-text, #fff);
        padding: 0px; 
        margin: 8px 12px;
        font-size: 0.8rem;
        font-family: "Monaco";
        background-color: var(--scoresheet-surface, #333);
      }
      
      && {
        .MuiInputLabel-root {
            color: var(--scoresheet-text, #fff);
        }
      }
      
      &:hover {
            background-color: var(--scoresheet-surface, #333);
          border: none;
        }

      @media (max-width: 1000px) {
        * {
          font-size: 1.05rem;
        }

        div > input {
          margin: 0.55rem 0.75rem;
          font-size: 0.96rem;
        }
      }
    `



    const StyledTable = styled(Table)`
      width: 100%;
      table-layout: fixed;

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

      @media (max-width: 919px) {
        & .MuiTableCell-root:first-child {
          width: 36%;
        }

        & .MuiTableCell-root:nth-last-child(2) {
          width: 18%;
        }

        & .MuiTableCell-root:last-child {
          width: 3.2rem;
        }

        & .MuiTableCell-root.selected-column {
          width: auto;
        }
      }
    `;

    const MetadataSection = styled.div`
      display: flex;
      justify-content: center;
      padding: 0.08rem 0 0.9rem;

      @media (max-width: 1000px) {
        margin-top: -0.42rem;
        padding: 0 0 0.38rem;
      }
    `;

    const MetadataGrid = styled.div`
      width: min(100%, 960px);
      display: grid;
      grid-template-columns: repeat(3, minmax(180px, 220px));
      justify-content: center;
      gap: 0.85rem;
      padding: 0 0.75rem;

      @media (max-width: 1000px) {
        width: min(100%, 1080px);
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.55rem;
      }

      @media (max-width: 919px) {
        grid-template-columns: minmax(0, 1fr);
        width: min(100%, 32rem);
      }
    `;

    const MetadataField = styled.div`
      display: flex;
      flex-direction: column;
      align-items: stretch;
      width: 100%;
    `;

    const MetadataFieldLabel = styled.div`
      color: var(--scoresheet-text, #fff);
      text-align: center;
      font-family: Monaco;
      font-size: 0.8rem;
      margin-bottom: 0.35rem;

      @media (max-width: 1000px) {
        font-size: 0.92rem;
      }
    `;

    const MetadataNotesField = styled(TextField)`
      && {
        width: 100%;
      }

      && .MuiInputBase-root {
        background-color: var(--scoresheet-surface, #333);
        color: var(--scoresheet-text, #fff);
        font-family: "Monaco";
        border-radius: 0;
        padding: 0;
      }

      && .MuiOutlinedInput-notchedOutline {
        border: none;
      }

      && textarea {
        color: var(--scoresheet-text, #fff);
        font-family: "Monaco";
        font-size: 0.9rem;
        line-height: 1.4;
        padding: 0.35rem 0.55rem;
        text-align: center;
        white-space: pre-wrap;
      }

      && textarea::placeholder {
        color: var(--scoresheet-text-muted, rgba(255, 255, 255, 0.5));
        opacity: 1;
        text-align: center;
      }

      @media (max-width: 1000px) {
        && textarea {
          font-size: 1rem;
          line-height: 1.3;
          padding: 0.38rem 0.5rem;
          min-height: 4.35rem !important;
        }
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

      @media (max-width: 1000px) {
        gap: 0.55rem;
      }
    `;

    const MetadataActionButtons = styled.div`
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 0.55rem;
      flex-wrap: wrap;

      & > button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }

      @media (max-width: 1000px) {
        width: min(100%, 26rem);

        & > button {
          flex: 1 1 10.75rem;
          font-size: 0.94rem;
          min-height: 2.4rem;
          white-space: nowrap;
        }
      }
    `;

    const DetailsPanelCell = styled(TableCell)`
      && {
        padding: 0.55rem 0.65rem;
        background-color: var(--scoresheet-surface, #333);
        border-bottom: none;
      }

      @media (max-width: 1000px) {
        && {
          padding: 0.45rem;
        }
      }
    `;

    const DetailsPanel = styled.div`
      display: grid;
      gap: 0.6rem;
    `;

    const MobileDetailsPanelShell = styled.div`
      padding: 0.45rem;
      background-color: var(--scoresheet-surface, #333);

      @media (min-width: 1001px) {
        display: none;
      }
    `;

    const DetailsSection = styled.div`
      display: grid;
      gap: 0.55rem;
      padding: 0.6rem;
      background: var(--scoresheet-detail-panel, rgba(20, 20, 20, 0.35));
      border: 1px solid rgba(30, 118, 98, 0.7);

      @media (max-width: 1000px) {
        padding: 0.5rem;
        gap: 0.45rem;
      }
    `;

    const DetailsSectionTitle = styled.div`
      color: var(--scoresheet-text, #fff);
      font-family: Monaco;
      font-size: 0.92rem;
      font-weight: 700;
      letter-spacing: 0.01em;

      @media (max-width: 1000px) {
        font-size: 0.98rem;
      }
    `;

    const DetailsRoundGrid = styled.div`
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 0.6rem;
    `;

    const DetailsRoundCard = styled.div`
      display: grid;
      gap: 0.5rem;
      padding: 0.55rem;
      background: var(--scoresheet-surface-alt, #333);
      border: 1px solid rgba(30, 118, 98, 0.58);
    `;

    const DetailsRoundTitle = styled.div`
      color: var(--scoresheet-text, #fff);
      font-family: Monaco;
      font-size: 0.9rem;
      font-weight: 700;
      text-align: center;
      word-break: break-word;
    `;

    const DetailsFieldGrid = styled.div`
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.5rem;

      @media (max-width: 1100px) {
        grid-template-columns: minmax(0, 1fr);
      }
    `;

    const DetailsField = styled.div`
      display: flex;
      flex-direction: column;
      gap: 0.28rem;
      min-width: 0;
    `;

    const DetailsToggleGrid = styled.div`
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.15rem 0.55rem;

      @media (max-width: 1000px) {
        grid-template-columns: minmax(0, 1fr);
      }
    `;

    const DetailToggleLabel = styled(FormControlLabel)`
      && {
        margin: 0;
        color: var(--scoresheet-text, #fff);
      }

      && .MuiTypography-root {
        color: var(--scoresheet-text, #fff);
        font-family: Monaco;
        font-size: 0.82rem;
      }

      && .MuiCheckbox-root {
        color: #1e7662;
        padding: 4px;
      }

      && .MuiCheckbox-root.Mui-checked {
        color: #2c9d84;
      }
    `;

    const CoopRowToggleLabel = styled(DetailToggleLabel)`
      && {
        width: 100%;
        justify-content: center;
      }

      && .MuiTypography-root {
        font-size: 0.84rem;
      }

      && .MuiCheckbox-root {
        padding: 4px;
        transform: scale(1.18);
      }
    `;

    const DetailTextField = styled(TextField)`
      && {
        width: 100%;
      }

      && .MuiInputBase-root {
        background-color: var(--scoresheet-surface, #333);
        color: var(--scoresheet-text, #fff);
        font-family: Monaco;
        border-radius: 0;
      }

      && .MuiOutlinedInput-notchedOutline {
        border-color: #1e7662;
      }

      &&:hover .MuiOutlinedInput-notchedOutline {
        border-color: #2c9d84;
      }

      && .Mui-focused .MuiOutlinedInput-notchedOutline {
        border-color: #2c9d84;
      }

      && .MuiInputBase-input,
      && .MuiInputBase-inputMultiline {
        color: var(--scoresheet-text, #fff);
        font-family: Monaco;
        font-size: 0.84rem;
        padding: 0.45rem 0.55rem;
      }

      @media (max-width: 1000px) {
        && .MuiInputBase-input,
        && .MuiInputBase-inputMultiline {
          font-size: 0.94rem;
        }
      }
    `;

    const StylePointsGrid = styled.div`
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 0.45rem 0.6rem;
    `;

    const StylePointRow = styled.label`
      display: grid;
      grid-template-columns: minmax(0, 1fr) 5.25rem;
      align-items: center;
      gap: 0.45rem;
      color: var(--scoresheet-text, #fff);
      font-family: Monaco;
      font-size: 0.82rem;
      min-width: 0;
    `;

    const StylePointName = styled.span`
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    `;

    const CompactTopControlGroup = styled.div`
      display: flex;
      align-items: center;
      justify-content: center;
      max-width: 100%;
      min-width: 0;
      gap: 0.55rem;
      flex-wrap: nowrap;

      @media (min-width: 1001px) {
        display: contents;
      }

      @media (max-width: 1000px) {
        gap: 0.4rem;
      }
    `;

    const PlayerNameStack = styled.div`
      display: flex;
      justify-content: center;
    `;

    const PlayerNameAnchor = styled.span`
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.7rem;
    `;

    const PlayerNameLabel = styled.span`
      position: relative;
      display: inline-flex;
      align-items: flex-start;
      justify-content: center;
      padding-top: 0.1rem;
    `;

    const PlayerAvatarIcon = styled.img`
      width: 24px;
      height: 24px;
      border-radius: 50%;
      object-fit: cover;
      flex-shrink: 0;
      margin-left: 0.15rem;
      border: 1px solid var(--scoresheet-border-soft, rgba(255, 255, 255, 0.22));
      box-shadow: 0 0 0 1px var(--scoresheet-avatar-shadow, rgba(0, 0, 0, 0.18));
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

          .MuiPickersPopper-root .MuiPaper-root,
          .MuiDialog-root .MuiPickersLayout-root,
          .MuiPickersLayout-root {
            background-color: var(--scoresheet-menu-bg, #333);
            color: var(--scoresheet-text, #fff);
            border: 1px solid #1e7662;
            border-radius: 0;
            box-shadow: 0 16px 36px rgba(0, 0, 0, 0.45);
            font-family: Monaco, monospace;
          }

          .MuiPickersLayout-root *,
          .MuiPickersPopper-root .MuiPaper-root * {
            font-family: Monaco, monospace;
          }

          .MuiPickersCalendarHeader-root,
          .MuiPickersCalendarHeader-label,
          .MuiDayCalendar-weekDayLabel,
          .MuiPickersArrowSwitcher-root,
          .MuiPickersArrowSwitcher-button,
          .MuiPickersArrowSwitcher-button .MuiSvgIcon-root,
          .MuiPickersYear-yearButton,
          .MuiPickersMonth-monthButton,
          .MuiPickersToolbar-root,
          .MuiPickersToolbar-content,
          .MuiPickersToolbarText-root,
          .MuiPickersLayout-actionBar button {
            color: var(--scoresheet-text, #fff) !important;
          }

          .MuiDayCalendar-weekDayLabel,
          .MuiPickersDay-root.Mui-disabled,
          .MuiPickersYear-yearButton.Mui-disabled,
          .MuiPickersMonth-monthButton.Mui-disabled {
            color: var(--scoresheet-text-muted, rgba(255, 255, 255, 0.52)) !important;
          }

          .MuiPickersDay-root,
          .MuiPickersYear-yearButton,
          .MuiPickersMonth-monthButton {
            color: var(--scoresheet-text, #fff) !important;
            background-color: transparent;
          }

          .MuiPickersDay-root:hover,
          .MuiPickersYear-yearButton:hover,
          .MuiPickersMonth-monthButton:hover,
          .MuiPickersLayout-actionBar button:hover {
            background-color: var(--scoresheet-menu-hover, rgba(30, 118, 98, 0.22));
          }

          .MuiPickersDay-root.Mui-selected,
          .MuiPickersYear-yearButton.Mui-selected,
          .MuiPickersMonth-monthButton.Mui-selected {
            background-color: #1e7662 !important;
            color: #fff !important;
          }

          .MuiPickersDay-root.MuiPickersDay-today:not(.Mui-selected) {
            border-color: #1e7662;
          }

          .MuiPickersPopper-root .MuiPaper-root .MuiIconButton-root,
          .MuiDialog-root .MuiPickersLayout-root .MuiIconButton-root {
            color: var(--scoresheet-text, #fff) !important;
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
          {streak >= 5 && (
            <path d="M12 0.9L13.1 2.4L14.7 2.9L13.5 4.1L13.8 5.8L12 4.9L10.2 5.8L10.5 4.1L9.3 2.9L10.9 2.4Z" fill={theme.sparkle} opacity="0.98" />
          )}
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
      <rect x="3.8" y="12.1" width="3.2" height="1.9" rx="0.95" fill={theme.frameStroke} />
      <rect x="27" y="12.1" width="3.2" height="1.9" rx="0.95" fill={theme.frameStroke} />
      <rect x="6.1" y="10.2" width="10.8" height="8.4" rx="2.7" fill={theme.frameStroke} />
      <rect x="17.1" y="10.2" width="10.8" height="8.4" rx="2.7" fill={theme.frameStroke} />
      <rect x="7.3" y="11.3" width="8.4" height="6.1" rx="1.9" fill="#050505" />
      <rect x="18.3" y="11.3" width="8.4" height="6.1" rx="1.9" fill="#050505" />
      <rect x="15.2" y="12.2" width="3.6" height="2.2" rx="1.1" fill={theme.frameStroke} />
      <rect x="6.9" y="10.9" width="9.2" height="1.05" rx="0.52" fill={theme.rimHighlight} opacity="0.8" />
      <rect x="17.9" y="10.9" width="9.2" height="1.05" rx="0.52" fill={theme.rimHighlight} opacity="0.8" />
      {theme?.sparkle && (
        <>
          <rect x="8.8" y="8.9" width="1.1" height="3.6" rx="0.5" fill={theme.sparkleColor} opacity="0.92" />
          <rect x="7.55" y="10.15" width="3.6" height="1.1" rx="0.5" fill={theme.sparkleColor} opacity="0.92" />
          <rect x="24.8" y="8.5" width="1.05" height="3.2" rx="0.5" fill={theme.sparkleColor} opacity="0.88" />
          <rect x="23.7" y="9.6" width="3.2" height="1.05" rx="0.5" fill={theme.sparkleColor} opacity="0.88" />
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
    const [secondaryRoundCreators, setSecondaryRoundCreators] = useState({});
    const [scores, setScores] = useState({});
    const [medianScores, setMedianScores] = useState([]);
    const [isSortAscending, setIsSortAscending] = useState(true);
    const [dates, setDates] = useState([]);
    const sortedDates = useMemo(() => {
                                return [...dates].sort().reverse(); // or any other sorting logic you have
                            }, [dates]);
    const requestedDate = useMemo(() => {
      if (typeof window === 'undefined') {
        return '';
      }

      const urlParams = new URLSearchParams(window.location.search);
      const dateParam = urlParams.get('date') || '';
      return /^\d{4}-\d{2}-\d{2}$/.test(dateParam) ? dateParam : '';
    }, []);
    const [selectedDate, setSelectedDate] = useState('');
    const [loadedRoundsDate, setLoadedRoundsDate] = useState('');
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
    const [saveRequestCount, setSaveRequestCount] = useState(0);
    const [openDatePicker, setOpenDatePicker] = useState(false);
    const [datePickerDraftValue, setDatePickerDraftValue] = useState(null);
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
    const [scoreCellMenu, setScoreCellMenu] = useState({
      mouseX: null,
      mouseY: null,
      playerField: '',
      playerDisplayName: '',
      roundTitle: '',
      secondaryJokerMode: false,
    });
    const [jokerRouletteHighlights, setJokerRouletteHighlights] = useState({});
    const [jokerRouletteSpinningPlayers, setJokerRouletteSpinningPlayers] = useState({});

    const playerNamesDisplay = useMemo(
      () => (players || []).map(getDisplayNameForPlayerField),
      [players]
    );
    const playerIconMap = useMemo(() => readPlayerIconMap(), []);
    const playerColorMap = useMemo(
      () => ({
        ...basePlayerColorMapping,
        ...readPlayerColorMap(),
      }),
      [],
    );
    activePlayerColorMapping = playerColorMap;

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
    const isLightProfileTheme = typeof document !== 'undefined' && document.body?.dataset?.profileTheme === 'light';
    const dateFieldBg = isLightProfileTheme ? '#f4f1e8' : '#333';
    const dateFieldText = isLightProfileTheme ? '#1b2530' : '#fff';
    const isSmallScreen = useMediaQuery(theme.breakpoints.down('sm'));
    const isCompactScreen = useMediaQuery('(max-width:1000px)');
    const isMobileView = useMediaQuery('(max-width:750px)');

    const fallbackBaseUrl = "https://hailsciencetrivia.com";
    const url =
      typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin.replace(/\/$/, '')
        : fallbackBaseUrl;
    const scoresheetBootstrapUrl = `${url}/api/v1/scoresheet-bootstrap/`;
    const scoresheetPresentationMetaUrl = `${url}/api/v1/scoresheet-presentation-meta/`;

    const wsRef = useRef(null);
    const pingIntervalRef = useRef(null);
    const clientIdRef = useRef(createClientId());
    const pendingMutationIdsRef = useRef(new Set());
    const serverRoundSnapshotRef = useRef({});
    const serverPresentationSnapshotRef = useRef(makePresentationSnapshot(null));
    const stylePointAnchorRefs = useRef({});
    const scoreCellLongPressTimeoutRef = useRef(null);
    const newPlayerInputRef = useRef(null);
    const datePickerFieldRef = useRef(null);
    const jokerRouletteTimeoutsRef = useRef({});
    const saveInFlightRef = useRef(false);
    const saveQueuedRef = useRef(false);
    const latestStateRef = useRef(null);
    const presentationHydrationKeyRef = useRef('');
    const prevUpdateFlagRef = useRef(0);
    const lastHydratedRoundsDateRef = useRef('');
    const roundsRef = useRef(rounds);
    const defaultPlayersRef = useRef(defaultPlayers);
    const tempTitlesLengthRef = useRef(tempTitles.length);
    const tempLinksLengthRef = useRef(tempLinks.length);
    const isVisible = usePageVisibility();
    const websocketUrl =
      typeof window !== 'undefined' && window.location?.host
        ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/scoresheet/`
        : `${fallbackBaseUrl.replace(/^http/, 'ws')}/ws/scoresheet/`;

    useEffect(() => {
      roundsRef.current = rounds;
    }, [rounds]);

    useEffect(() => {
      defaultPlayersRef.current = defaultPlayers;
    }, [defaultPlayers]);

    useEffect(() => {
      tempTitlesLengthRef.current = tempTitles.length;
    }, [tempTitles.length]);

    useEffect(() => {
      tempLinksLengthRef.current = tempLinks.length;
    }, [tempLinks.length]);

    const markDirty = useCallback(() => {
      setIsSaved(false);
      setSaveRequestCount(prev => prev + 1);
    }, []);

    const transformName = useCallback((name) => {
      if (name === 'Dad') {
        return 'Dan';
      } else if (name === 'Mom') {
        return 'Debi';
      } else {
        return name;
      }
    }, []);

    const getNormalizedCreatorName = useCallback((name) => transformName(name || ''), [transformName]);

    const getRoundCreatorPair = useCallback((roundTitle, roundOverride = null) => {
      const round = roundOverride || rounds.find(candidate => candidate.title === roundTitle);
      return [
        roundCreators[roundTitle] || round?.creator || '',
        secondaryRoundCreators[roundTitle] || round?.secondary_creator || '',
      ].map(getNormalizedCreatorName);
    }, [getNormalizedCreatorName, roundCreators, rounds, secondaryRoundCreators]);

    const getRoundCreatorDisplayNames = useCallback((roundTitle, roundOverride = null) => {
      return getRoundCreatorPair(roundTitle, roundOverride).filter(Boolean);
    }, [getRoundCreatorPair]);

    const roundIncludesCreator = useCallback((roundTitle, playerDisplayName, roundOverride = null) => {
      return getRoundCreatorDisplayNames(roundTitle, roundOverride).includes(playerDisplayName);
    }, [getRoundCreatorDisplayNames]);

    const normalizeSelectedJokerSelection = useCallback((selection) => {
      if (Array.isArray(selection)) {
        return [...new Set(selection.filter(title => title && title !== 'Select'))].slice(0, 2);
      }
      if (selection && selection !== 'Select') {
        return [selection];
      }
      return [];
    }, []);

    const buildStoredJokerSelection = useCallback((roundTitles) => {
      const normalizedTitles = normalizeSelectedJokerSelection(roundTitles);
      if (!normalizedTitles.length) {
        return 'Select';
      }
      return normalizedTitles.length === 1 ? normalizedTitles[0] : normalizedTitles;
    }, [normalizeSelectedJokerSelection]);

    const getSelectedJokerRoundsForPlayer = useCallback((playerField) => {
      return normalizeSelectedJokerSelection(selectedRounds[playerField]);
    }, [normalizeSelectedJokerSelection, selectedRounds]);

    const getPrimaryJokerRoundForPlayer = useCallback((playerField) => {
      return getSelectedJokerRoundsForPlayer(playerField)[0] || 'Select';
    }, [getSelectedJokerRoundsForPlayer]);

    const getDisplayedJokerSelectionLabel = useCallback((playerField) => {
      const selectedTitles = getSelectedJokerRoundsForPlayer(playerField);
      if (!selectedTitles.length) {
        return '- Select -';
      }
      if (selectedTitles.length === 1) {
        return selectedTitles[0];
      }
      return `${selectedTitles[0]} + ${selectedTitles[1]}`;
    }, [getSelectedJokerRoundsForPlayer]);

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

    const getApiHeaders = useCallback((extraHeaders = {}) => {
      const nextHeaders = { ...extraHeaders };
      if (typeof window === 'undefined') {
        return nextHeaders;
      }

      const token = window.localStorage.getItem('token');
      if (token) {
        nextHeaders.Authorization = `Token ${token}`;
      }

      return nextHeaders;
    }, []);

    useEffect(() => {
      let isCancelled = false;
      const controller = new AbortController();
      const params = new URLSearchParams();
      const requestedScoresheetDate = selectedDate || requestedDate;
      if (requestedScoresheetDate) {
        params.set('date', requestedScoresheetDate);
      }

      fetch(`${scoresheetBootstrapUrl}${params.toString() ? `?${params.toString()}` : ''}`, {
            headers: getApiHeaders(),
            credentials: 'same-origin',
            signal: controller.signal,
        })
        .then(response => {
          console.log('Initial response: ', response);
          if (!response.ok) {
            throw new Error("HTTP error " + response.status);
          }
          return response.json();
        })
        .then(payload => {
            if (isCancelled) {
                return;
            }
            const bootstrapRounds = Array.isArray(payload.rounds) ? payload.rounds : [];
            const uniqueDates = Array.isArray(payload.dates) ? payload.dates : [];
            setAllPlayers(Array.isArray(payload.creator_options) ? payload.creator_options : []);
            setMajorCategories(Array.isArray(payload.major_categories) ? payload.major_categories : []);
            setMinor1Categories(Array.isArray(payload.minor_categories) ? payload.minor_categories : []);
            setMinor2Categories(Array.isArray(payload.minor_categories) ? payload.minor_categories : []);
            setDates(prevDates => {
                if (
                    prevDates.length === uniqueDates.length &&
                    prevDates.every((value, index) => value === uniqueDates[index])
                ) {
                    return prevDates;
                }
                return uniqueDates;
            });

            const effectiveSelectedDate = payload.selected_date || resolveScoresheetDate(selectedDate, requestedDate, uniqueDates);
            if (!effectiveSelectedDate) {
                setRounds([]);
                setPlayers(defaultPlayers);
                setLoadedRoundsDate('');
                return;
            }

            if (selectedDate !== effectiveSelectedDate) {
                setSelectedDate(effectiveSelectedDate);
            }

            const nextRoundSnapshot = {};
            bootstrapRounds.forEach(round => {
              nextRoundSnapshot[round.id] = makeRoundSnapshot(round);
            });
            serverRoundSnapshotRef.current = nextRoundSnapshot;
            setRounds(bootstrapRounds);
            setLoadedRoundsDate(effectiveSelectedDate);

            if (
                prevUpdateFlagRef.current !== updateFlag ||
                lastHydratedRoundsDateRef.current !== effectiveSelectedDate ||
                tempTitlesLengthRef.current === 0
            ) {
                setTempTitles(bootstrapRounds.map(round => round.title));
            }

            if (
                prevUpdateFlagRef.current !== updateFlag ||
                lastHydratedRoundsDateRef.current !== effectiveSelectedDate ||
                tempLinksLengthRef.current === 0
            ) {
                setTempLinks(bootstrapRounds.map(round => round.link));
            }

            prevUpdateFlagRef.current = updateFlag;
            lastHydratedRoundsDateRef.current = effectiveSelectedDate;


          let initialCooperativeStatus = {};
            bootstrapRounds.forEach(round => {
              initialCooperativeStatus[round.title] = round.cooperative || false;
            });
            setCooperativeStatus(initialCooperativeStatus);

            let initialReplayStatus = {};
            bootstrapRounds.forEach(round => {
                initialReplayStatus[round.title] = round.replay || false;
            });
            setIsReplay(initialReplayStatus);

            // also set the initial Major Categories
            let initialMajorCategories = {};
            bootstrapRounds.forEach(round => {
                initialMajorCategories[round.title] = round.major_category || '';
            });
            setSelectedMajorCategories(initialMajorCategories);

            // also set the initial Minor Categories
            let initialMinor1Categories = {};
            bootstrapRounds.forEach(round => {
                initialMinor1Categories[round.title] = round.minor_category1 || '';
            });
            setSelectedMinor1Categories(initialMinor1Categories);

            // also set the initial Minor Categories
            let initialMinor2Categories = {};
            bootstrapRounds.forEach(round => {
                initialMinor2Categories[round.title] = round.minor_category2 || '';
            });
            setSelectedMinor2Categories(initialMinor2Categories);

            // also set the initial Max Scores
            let initialMaxScores = {};
            bootstrapRounds.forEach(round => {
                initialMaxScores[round.title] = round.max_score || 10;
            });
            setMaxScores(initialMaxScores);

          let roundCreators = {};
          let secondaryCreators = {};
          for (let round of bootstrapRounds) {
            roundCreators[round.title] = round.creator;
            secondaryCreators[round.title] = round.secondary_creator || '';
          }
          roundCreators = Object.keys(roundCreators).reduce((acc, key) => {
            acc[key] = getNormalizedCreatorName(roundCreators[key]);
            return acc;
          }, {});
          secondaryCreators = Object.keys(secondaryCreators).reduce((acc, key) => {
            acc[key] = getNormalizedCreatorName(secondaryCreators[key]);
            return acc;
          }, {});
          setRoundCreators(roundCreators);
          setSecondaryRoundCreators(secondaryCreators);

          // start by setting the playerNames to the default players
            let playerNames = [...defaultPlayers, ...extractPlayersFromRounds(bootstrapRounds)];

          // Get unique player names
          playerNames = [...new Set(playerNames)];
          // setPlayers(playerNames);

          const initialScores = {};
          playerNames.forEach(player => {
            initialScores[player] = {};
            bootstrapRounds.forEach(round => {
              initialScores[player][round.title] = getMergedRoundScoreMap(round)[player] ?? null;
            });
          });
          setScores(initialScores);
        })
        .catch(function(error) {
            if (isCancelled || error?.name === 'AbortError') {
                return;
            }
            //setErrorMessage("Failed to fetch rounds");
        });

        return () => {
            isCancelled = true;
            controller.abort();
        };
    }, [defaultPlayers, getApiHeaders, getNormalizedCreatorName, requestedDate, scoresheetBootstrapUrl, selectedDate, updateFlag]);

    useEffect(() => {
        if (!selectedDate || loadedRoundsDate !== selectedDate) {
            return undefined;
        }

        const hydrationKey = `${selectedDate}:${updateFlag}`;
        const shouldHydrateFromServer =
          isSavedRef.current || presentationHydrationKeyRef.current !== hydrationKey;

        if (!shouldHydrateFromServer) {
            return undefined;
        }

        let isCancelled = false;

        const params = new URLSearchParams();
        params.set('date', selectedDate);

        fetch(`${scoresheetPresentationMetaUrl}?${params.toString()}`, {
            headers: getApiHeaders(),
            credentials: 'same-origin',
        })
        .then(response => {
          console.log('Initial response: ', response);
          if (!response.ok) {
            throw new Error("HTTP error " + response.status);
          }
          return response.json();
        })
        .then(payload => {
            if (isCancelled) {
                return;
            }
            if (!isSavedRef.current && presentationHydrationKeyRef.current === hydrationKey) {
                return;
            }

            presentationHydrationKeyRef.current = hydrationKey;
            const crownHistory = Array.isArray(payload.crown_history) ? payload.crown_history : [];
            setPresentations(crownHistory);
            const selectedPresentation = payload.selected_presentation || null;
            serverPresentationSnapshotRef.current = makePresentationSnapshot(selectedPresentation);

            let plist = null;
            if(selectedPresentation) {
                plist = selectedPresentation.player_list;
            }
            const resolvedPlayers = [...new Set([
                ...resolvePresentationPlayers(plist, defaultPlayersRef.current),
                ...extractPlayersFromRounds(roundsRef.current),
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
                setInheritedCrownedWinner(getInheritedCrownedWinner(crownHistory, selectedDate));
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
                setInheritedCrownedWinner(getInheritedCrownedWinner(crownHistory, selectedDate));
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
    }, [defaultHost, getApiHeaders, loadedRoundsDate, scoresheetPresentationMetaUrl, selectedDate, updateFlag]);

    useEffect(() => {
      if (players.length > 0 && rounds.length > 0) {

        // Compute median scores
        const medianScores = rounds.map(round => {
            const creatorFields = new Set(
              getRoundCreatorDisplayNames(round.title, round)
                .map(creatorName => getScoreFieldForName(creatorName))
                .filter(scoreField => players.includes(scoreField))
            );
            const scores = Object.entries(getMergedRoundScoreMap(round))
              .filter(([scoreKey, scoreValue]) => !creatorFields.has(scoreKey) && typeof scoreValue === 'number')
              .map(([, scoreValue]) => scoreValue);

            if (!scores.length) {
              return null;
            }

            scores.sort((a, b) => a - b);

            let median;
            if (scores.length % 2 === 0) { // even length
              median = (scores[scores.length / 2 - 1] + scores[scores.length / 2]) / 2;
            } else { // odd length
              median = scores[Math.floor(scores.length / 2)];
            }

            return median;
        });
        setMedianScores(medianScores);
      }
    }, [getRoundCreatorDisplayNames, players, rounds]);

    useEffect(() => {
        console.log('sortedDates:', sortedDates);

      if (dates.length > 0 && !isDatesInitialized) {
        const initialDate = requestedDate && sortedDates.includes(requestedDate)
          ? requestedDate
          : sortedDates[0];
        setSelectedDate(initialDate);
        setIsDatesInitialized(true);
      }
    }, [dates, isDatesInitialized, requestedDate, sortedDates]);

    const isSavedRef = useRef(isSaved);

    useEffect(() => {
       isSavedRef.current = isSaved;
    }, [isSaved]);

    useEffect(() => {
      latestStateRef.current = {
        rounds,
        selectedRounds,
        roundCreators,
        secondaryRoundCreators,
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
      secondaryRoundCreators,
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
                const originalRound = updatedRounds[roundIndex];
                const updatedRound = applyCooperativeScoreEntry({
                    round: originalRound,
                    playerField: player,
                    newScore,
                    players,
                    creatorNames: getRoundCreatorDisplayNames(roundTitle, round),
                    isCooperative: Boolean(cooperativeStatus[roundTitle]),
                });
                const originalScoreMap = getMergedRoundScoreMap(originalRound);
                const updatedScoreMap = getMergedRoundScoreMap(updatedRound);
                updatedRounds[roundIndex] = updatedRound;
                setRounds(updatedRounds);

                setScores(prevScores => {
                    const nextScores = { ...prevScores };
                    Object.entries(updatedScoreMap).forEach(([playerField, scoreValue]) => {
                        if (originalScoreMap[playerField] === scoreValue) {
                            return;
                        }
                        nextScores[playerField] = {
                            ...(nextScores[playerField] || {}),
                            [roundTitle]: scoreValue,
                        };
                    });
                    return nextScores;
                });
            }
        }
        markDirty();
    };


    const handleRemovePlayer = (playerToRemove) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;

      const displayName = getDisplayNameForPlayerField(playerToRemove);
      const confirmDeletePlayer = window.confirm(
        `Are you sure you want to delete ${displayName || 'this player'} and all scores?`,
      );
      if (!confirmDeletePlayer) return;

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
            setLoadedRoundsDate('');
            // check if the eventOrDate.target.value exists in the sorted dates array
            // and if it doesn't run:
            //  setSelectedDate(todayStr);
            //  setTempTitles([]);
            //  setPresID(0);

            if (!sortedDates.includes(nextDate)) {
                // setDates(prevDates => [...prevDates, eventOrDate.target.value]);
                setSelectedDate(nextDate);
                setRounds([]);
                setTempTitles([]);
                setTempLinks([]);
                setPresID(0);
                return;
            }

            setSelectedDate(nextDate);
            setRounds([]);
            setTempTitles([]);
            setTempLinks([]);
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
                  const updatedSelection = normalizeSelectedJokerSelection(newSelectedRounds[player]).map(title => (
                    title === oldTitle ? newTitle : title
                  ));
                  newSelectedRounds[player] = buildStoredJokerSelection(updatedSelection);
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
          maxDelay: 720,
          easingPower: 1.75,
          fastDurationMs: 500,
          slowdownCycles: 3,
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
          [player]: buildStoredJokerSelection([finalTitle]),
        }));
        clearJokerRouletteForPlayer(player);
        markDirty();
      }, elapsedDelay + 240));

      jokerRouletteTimeoutsRef.current[player] = timeoutIds;
    }, [buildStoredJokerSelection, clearJokerRouletteForPlayer, markDirty, rounds]);

    const handleJokerSelectionChange = useCallback((player, nextValue, options = {}) => {
      if (!options.skipConfirm && !confirmPastChange()) return;

      if (nextValue === JOKER_RANDOMIZE_VALUE) {
        startJokerRoulette(player);
        return;
      }

      clearJokerRouletteForPlayer(player);
      setSelectedRounds(prevState => {
        const currentSelection = normalizeSelectedJokerSelection(prevState[player]);
        let nextSelection;

        if (options.clearRound) {
          nextSelection = currentSelection.filter(title => title !== options.clearRound);
        } else if (options.addSecondary) {
          const withoutSelectedTitle = currentSelection.filter(title => title !== nextValue);
          if (!nextValue || nextValue === 'Select') {
            nextSelection = withoutSelectedTitle;
          } else if (withoutSelectedTitle.length === 0) {
            nextSelection = [nextValue];
          } else {
            nextSelection = [withoutSelectedTitle[0], nextValue];
          }
        } else {
          nextSelection = nextValue && nextValue !== 'Select' ? [nextValue] : [];
        }

        return {
          ...prevState,
          [player]: buildStoredJokerSelection(nextSelection),
        };
      });
      markDirty();
    }, [buildStoredJokerSelection, clearJokerRouletteForPlayer, markDirty, normalizeSelectedJokerSelection, startJokerRoulette]);

    const clearScoreCellLongPress = useCallback(() => {
      if (scoreCellLongPressTimeoutRef.current) {
        window.clearTimeout(scoreCellLongPressTimeoutRef.current);
        scoreCellLongPressTimeoutRef.current = null;
      }
    }, []);

    const closeScoreCellMenu = useCallback(() => {
      clearScoreCellLongPress();
      setScoreCellMenu({
        mouseX: null,
        mouseY: null,
        playerField: '',
        playerDisplayName: '',
        roundTitle: '',
        secondaryJokerMode: false,
      });
    }, [clearScoreCellLongPress]);

    const openScoreCellMenu = useCallback((clientX, clientY, playerField, roundTitle, options = {}) => {
      const playerDisplayName = getDisplayNameForPlayerField(playerField);
      if (!playerDisplayName || !roundTitle) {
        return;
      }

      setScoreCellMenu({
        mouseX: clientX + 2,
        mouseY: clientY - 6,
        playerField,
        playerDisplayName,
        roundTitle,
        secondaryJokerMode: Boolean(options.secondaryJokerMode),
      });
    }, []);

    const handleScoreCellContextMenu = useCallback((event, playerField, roundTitle) => {
      event.preventDefault();
      clearScoreCellLongPress();
      openScoreCellMenu(event.clientX, event.clientY, playerField, roundTitle, {
        secondaryJokerMode: event.altKey,
      });
    }, [clearScoreCellLongPress, openScoreCellMenu]);

    const handleScoreCellTouchStart = useCallback((event, playerField, roundTitle) => {
      clearScoreCellLongPress();
      const touch = event.touches?.[0];
      if (!touch) {
        return;
      }

      const { clientX, clientY } = touch;
      scoreCellLongPressTimeoutRef.current = window.setTimeout(() => {
        openScoreCellMenu(clientX, clientY, playerField, roundTitle);
      }, 450);
    }, [clearScoreCellLongPress, openScoreCellMenu]);

    useEffect(() => () => {
      clearScoreCellLongPress();
    }, [clearScoreCellLongPress]);

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

    const handleCrownWinnerClick = useCallback(() => {
      const nextWinnerField =
        getPlayerFieldForName(players, tiebreakWinner) || sortedPlayersForDisplay[0] || null;

      if (!nextWinnerField) {
        return;
      }

      const nextWinnerName = getDisplayNameForPlayer(nextWinnerField);

      if (nextWinnerName !== crownedWinner) {
        setCrownedWinner(nextWinnerName);
        setPresentations(prevPresentations => applyPresentationFieldsForSelectedDate(
          prevPresentations,
          selectedDate,
          { crowned_winner: nextWinnerName },
        ));
        markDirty();
      }
    }, [crownedWinner, markDirty, players, selectedDate, sortedPlayersForDisplay, tiebreakWinner]);

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
      const attemptBurst = (remainingAttempts) => {
        let anchorNode = stylePointAnchorRefs.current[playerField];

        if (!anchorNode) {
          anchorNode = Array.from(document.querySelectorAll('[data-player-field]'))
            .find((node) => node.dataset.playerField === playerField) || null;
        }

        if (!anchorNode) {
          if (remainingAttempts > 0) {
            window.setTimeout(() => attemptBurst(remainingAttempts - 1), 70);
          }
          return;
        }

        const rect = anchorNode.getBoundingClientRect();
        window.dispatchEvent(new CustomEvent('scoresheet:burst-stars', {
          detail: {
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
          },
        }));
      };

      attemptBurst(8);
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


    const handleRoundCreatorChange = (roundTitle, creatorSlot, newCreatorName) => {
      const normalizedCreatorName = getNormalizedCreatorName(newCreatorName);

      if (creatorSlot === 'secondary') {
        setSecondaryRoundCreators(prevRoundCreators => ({
          ...prevRoundCreators,
          [roundTitle]: normalizedCreatorName,
        }));
      } else {
        setRoundCreators(prevRoundCreators => ({
          ...prevRoundCreators,
          [roundTitle]: normalizedCreatorName,
        }));
      }

      const currentCreatorNames = getRoundCreatorPair(roundTitle);
      const nextCreatorNames = creatorSlot === 'secondary'
        ? [currentCreatorNames[0] || '', normalizedCreatorName]
        : [normalizedCreatorName, currentCreatorNames[1] || ''];

      setScores(prevScores => {
        return clearCreatorScoreForRound(prevScores, players, roundTitle, nextCreatorNames);
      });

      setRounds(prevRounds => {
        const newRounds = [...prevRounds];
        const roundIndex = newRounds.findIndex(round => round.title === roundTitle);
        if (roundIndex !== -1) {
          const nextRound = { ...newRounds[roundIndex] };
          nextRound.creator = nextCreatorNames[0] || '';
          nextRound.secondary_creator = nextCreatorNames[1] || '';

          nextCreatorNames.forEach(creatorName => {
            const creatorField = getScoreFieldForName(creatorName);
            if (!creatorField) {
              return;
            }

            nextRound[creatorField] = null;
            const currentExtraScores = getRoundExtraScores(nextRound);
            if (Object.prototype.hasOwnProperty.call(currentExtraScores, creatorField)) {
              const nextExtraScores = { ...currentExtraScores };
              delete nextExtraScores[creatorField];
              nextRound.extra_scores = nextExtraScores;
            }
          });

          newRounds[roundIndex] = nextRound;
        }
        return newRounds;
      });

      markDirty();
    };

    const handleCreatorChange = (roundTitle, newCreatorName) => {
      handleRoundCreatorChange(roundTitle, 'primary', newCreatorName);
    };

    const handleSecondaryCreatorChange = (roundTitle, newCreatorName) => {
      handleRoundCreatorChange(roundTitle, 'secondary', newCreatorName);
    };

    const handleSetCellAsJoker = useCallback(() => {
      if (!scoreCellMenu.playerField || !scoreCellMenu.roundTitle) {
        return;
      }

      const currentJokerRounds = getSelectedJokerRoundsForPlayer(scoreCellMenu.playerField);
      const jokerAction = getScoreCellJokerAction(
        currentJokerRounds,
        scoreCellMenu.roundTitle,
        scoreCellMenu.secondaryJokerMode,
      );

      if (jokerAction.mode === 'clear') {
        handleJokerSelectionChange(scoreCellMenu.playerField, scoreCellMenu.roundTitle, {
          clearRound: scoreCellMenu.roundTitle,
          skipConfirm: true,
        });
      } else if (jokerAction.mode === 'secondary') {
        handleJokerSelectionChange(scoreCellMenu.playerField, scoreCellMenu.roundTitle, {
          addSecondary: true,
          skipConfirm: true,
        });
      } else {
        handleJokerSelectionChange(scoreCellMenu.playerField, scoreCellMenu.roundTitle, {
          skipConfirm: true,
        });
      }
      closeScoreCellMenu();
    }, [
      closeScoreCellMenu,
      getSelectedJokerRoundsForPlayer,
      handleJokerSelectionChange,
      scoreCellMenu.playerField,
      scoreCellMenu.roundTitle,
      scoreCellMenu.secondaryJokerMode,
    ]);

    const handleSetCellAsCreator = useCallback(() => {
      if (!scoreCellMenu.playerDisplayName || !scoreCellMenu.roundTitle) {
        return;
      }

      if (!confirmPastChange()) {
        return;
      }

      handleCreatorChange(scoreCellMenu.roundTitle, scoreCellMenu.playerDisplayName);
      closeScoreCellMenu();
    }, [closeScoreCellMenu, scoreCellMenu.playerDisplayName, scoreCellMenu.roundTitle]);

    const scoreCellMenuJokerRounds = scoreCellMenu.playerField
      ? getSelectedJokerRoundsForPlayer(scoreCellMenu.playerField)
      : [];
    const scoreCellJokerMenuAction = getScoreCellJokerAction(
      scoreCellMenuJokerRounds,
      scoreCellMenu.roundTitle,
      scoreCellMenu.secondaryJokerMode,
    );
    const scoreCellJokerMenuLabel = scoreCellJokerMenuAction.label;

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
            headers: getApiHeaders({
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken,
            }),
            credentials: 'same-origin',
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
    }, [buildCurrentSavePayload, csrfToken, getApiHeaders, url]);

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
          headers: getApiHeaders({
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          }),
          credentials: 'same-origin',
          body,
          keepalive: true,
        }).catch(() => {});
      };

      window.addEventListener('pagehide', flushPendingSave);

      return () => {
        window.removeEventListener('pagehide', flushPendingSave);
      };
    }, [buildCurrentSavePayload, csrfToken, getApiHeaders, url]);

    const formatRoundData = (round, index) => {
      let formattedData = {
        creator: roundCreators[round.title] || '',
        secondary_creator: secondaryRoundCreators[round.title] || '',
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
            headers: getApiHeaders({
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            }),
            credentials: 'same-origin',
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
            headers: getApiHeaders({
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CSRFToken': csrfToken,
            }),
            credentials: 'same-origin',
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
            setSelectedRounds(prevSelectedRounds => {
              const nextSelectedRounds = { ...prevSelectedRounds };
              const deletedRound = rounds.find(round => round.id === roundId);
              if (!deletedRound) {
                return nextSelectedRounds;
              }
              Object.keys(nextSelectedRounds).forEach(playerField => {
                const filteredSelection = normalizeSelectedJokerSelection(nextSelectedRounds[playerField])
                  .filter(title => title !== deletedRound.title);
                nextSelectedRounds[playerField] = buildStoredJokerSelection(filteredSelection);
              });
              return nextSelectedRounds;
            });
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



  const roundNavigationControls = (
    <RoundNavigationStack>
      <RoundSwitchHelper>Select below to change round or date.</RoundSwitchHelper>
      <RoundNavigationControlGroup>
        <RoundDateFormControl>
          <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DatePicker
              open={openDatePicker}
              value={datePickerDraftValue || (selectedDate ? dayjs(selectedDate) : null)}
              views={['year', 'month', 'day']}
              onChange={(newValue) => {
                  setDatePickerDraftValue(newValue);
              }}
              onAccept={(newValue) => {
                  if (!newValue) {
                    return;
                  }
                  const formattedDate = dayjs(newValue).format('YYYY-MM-DD');
                  handleChangeDate(formattedDate);
                  setDatePickerDraftValue(null);
                  setOpenDatePicker(false);
              }}
              onClose={() => {
                  setDatePickerDraftValue(null);
                  setOpenDatePicker(false);
              }}
              slots={{
                  day: CustomDay,
              }}
              slotProps={{
                textField: {
                  ref: datePickerFieldRef,
                  onClick: () => {
                    setDatePickerDraftValue(selectedDate ? dayjs(selectedDate) : null);
                    setOpenDatePicker(true);
                  },
                  placeholder: 'Select date',
                  inputProps: {
                    readOnly: true,
                    style: {
                      cursor: 'pointer',
                    },
                  },
                  sx: {
                    minWidth: isMobileView ? '100%' : (isCompactScreen ? (isSmallScreen ? '9.1rem' : '9.7rem') : '9.5rem'),
                    maxWidth: isMobileView ? '100%' : (isCompactScreen ? (isSmallScreen ? '9.1rem' : '9.7rem') : '10.25rem'),
                    width: '100%',
                    margin: isCompactScreen ? 0 : '0.4rem',
                    backgroundColor: dateFieldBg,
                    '& .MuiInputBase-root': {
                      backgroundColor: `${dateFieldBg} !important`,
                      color: `${dateFieldText} !important`,
                      fontFamily: 'Monaco',
                      borderRadius: 0,
                      cursor: 'pointer',
                    },
                    '& .MuiOutlinedInput-root, & .MuiPickersInputBase-root, & .MuiPickersOutlinedInput-root': {
                      backgroundColor: `${dateFieldBg} !important`,
                      color: `${dateFieldText} !important`,
                    },
                    '& .MuiPickersSectionList-root, & .MuiPickersInputBase-sectionsContainer, & .MuiPickersSectionList-sectionContent, & .MuiInputBase-input': {
                      backgroundColor: `${dateFieldBg} !important`,
                      color: `${dateFieldText} !important`,
                    },
                    '& .MuiInputAdornment-root': {
                      marginLeft: 0,
                      marginRight: '0.2rem',
                    },
                    '& .MuiIconButton-root': {
                      color: `${dateFieldText} !important`,
                      padding: '4px',
                    },
                    '& .MuiOutlinedInput-notchedOutline': {
                      border: 'none',
                    },
                    '& input': {
                      color: dateFieldText,
                      fontFamily: 'Monaco',
                      textAlign: 'center',
                      fontSize: isCompactScreen ? '1rem' : undefined,
                      padding: isCompactScreen ? '10px 10px 10px 12px' : '8px 8px 8px 12px',
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
        </RoundDateFormControl>

        <RoundSwitchFormControl>
          <StyledInputLabel className={"showonsmall"}>Switch Round</StyledInputLabel>
            <RoundSwitchSelect
              className={"showonsmall"}
              inputProps={{ 'aria-label': 'Switch Round' }}
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
          </RoundSwitchSelect>
        </RoundSwitchFormControl>
      </RoundNavigationControlGroup>
    </RoundNavigationStack>
  );

  const detailsPanelContent = (
    <DetailsPanel>
      <DetailsSection>
        <DetailsSectionTitle>Round Details</DetailsSectionTitle>
        <DetailsRoundGrid>
          {rounds.map((round, index) => (
            <DetailsRoundCard key={round.id || round.title || index}>
              <DetailsRoundTitle>{round.title || `Round ${index + 1}`}</DetailsRoundTitle>
              <DetailsToggleGrid>
                <DetailToggleLabel
                  control={
                    <Checkbox
                      className="star-ricochet"
                      checked={Boolean(isReplay[round.title])}
                      onChange={(event) => handleReplayChange(round.title, event.target.checked)}
                    />
                  }
                  label="Replay"
                />
                <DetailToggleLabel
                  control={
                    <Checkbox
                      className="star-ricochet"
                      checked={Boolean(cooperativeStatus[round.title])}
                      onChange={(event) => handleCooperativeChange(round.title, event.target.checked)}
                    />
                  }
                  label="Co-op"
                />
              </DetailsToggleGrid>
              <DetailsFieldGrid>
                <DetailsField>
                  <MetadataFieldLabel>Max Score</MetadataFieldLabel>
                  <DetailTextField
                    value={maxScores[round.title] || 10}
                    onChange={(e) => handleMaxScoreChange(round.title, parseFloat(e.target.value))}
                    type="number"
                    inputProps={{ step: 0.5, min: 1, max: 100 }}
                  />
                </DetailsField>
                <DetailsField>
                  <MetadataFieldLabel>Creator</MetadataFieldLabel>
                  <MetadataFormControl>
                    <StyledSelect
                      MenuProps={dropdownMenuProps}
                      value={roundCreators[round.title] || ''}
                      onChange={(e) => handleCreatorChange(round.title, e.target.value)}
                    >
                      <MenuItem value="">Unknown</MenuItem>
                      {creatorOptions.map((player, creatorIndex) => (
                        <MenuItem key={creatorIndex} value={player}>
                          {player}
                        </MenuItem>
                      ))}
                    </StyledSelect>
                  </MetadataFormControl>
                </DetailsField>
                <DetailsField>
                  <MetadataFieldLabel>2nd Creator</MetadataFieldLabel>
                  <MetadataFormControl>
                    <StyledSelect
                      MenuProps={dropdownMenuProps}
                      value={secondaryRoundCreators[round.title] || ''}
                      onChange={(e) => handleSecondaryCreatorChange(round.title, e.target.value)}
                    >
                      <MenuItem value="">None</MenuItem>
                      {creatorOptions.map((player, creatorIndex) => (
                        <MenuItem key={creatorIndex} value={player}>
                          {player}
                        </MenuItem>
                      ))}
                    </StyledSelect>
                  </MetadataFormControl>
                </DetailsField>
                <DetailsField>
                  <MetadataFieldLabel>Category</MetadataFieldLabel>
                  <MetadataFormControl>
                    <StyledSelect
                      MenuProps={dropdownMenuProps}
                      value={selectedMajorCategories[round.title] || ''}
                      onChange={(e) => handleMajorCategoryChange(round.title, e.target.value)}
                    >
                      {majorCategories.sort((a, b) => a.localeCompare(b)).map((category, categoryIndex) => (
                        <MenuItem key={categoryIndex} value={category}>
                          {category}
                        </MenuItem>
                      ))}
                    </StyledSelect>
                  </MetadataFormControl>
                </DetailsField>
                <DetailsField>
                  <MetadataFieldLabel>Sub1</MetadataFieldLabel>
                  <MetadataFormControl>
                    <StyledSelect
                      MenuProps={dropdownMenuProps}
                      value={selectedMinor1Categories[round.title] || ''}
                      onChange={(e) => handleMinor1CategoryChange(round.title, e.target.value)}
                    >
                      {minor1Categories.sort((a, b) => a.localeCompare(b)).map((category, categoryIndex) => (
                        <MenuItem key={categoryIndex} value={category}>
                          {category}
                        </MenuItem>
                      ))}
                    </StyledSelect>
                  </MetadataFormControl>
                </DetailsField>
                <DetailsField>
                  <MetadataFieldLabel>Sub2</MetadataFieldLabel>
                  <MetadataFormControl>
                    <StyledSelect
                      MenuProps={dropdownMenuProps}
                      value={selectedMinor2Categories[round.title] || ''}
                      onChange={(e) => handleMinor2CategoryChange(round.title, e.target.value)}
                    >
                      {minor2Categories.sort((a, b) => a.localeCompare(b)).map((category, categoryIndex) => (
                        <MenuItem key={categoryIndex} value={category}>
                          {category}
                        </MenuItem>
                      ))}
                    </StyledSelect>
                  </MetadataFormControl>
                </DetailsField>
              </DetailsFieldGrid>
              <DetailsField>
                <MetadataFieldLabel>Slide Link</MetadataFieldLabel>
                <DetailTextField
                  value={tempLinks[index]}
                  onChange={(e) => handleTempLinkChange(index, e.target.value)}
                  onBlur={(e) => handleLinkChange(index, e.target.value)}
                  multiline
                  maxRows={2}
                />
              </DetailsField>
              <StyledButton type="button" onClick={() => handleRemoveColumn(round.id)} style={{ width: '100%', margin: 0 }}>
                Delete Round
              </StyledButton>
            </DetailsRoundCard>
          ))}
        </DetailsRoundGrid>
      </DetailsSection>

      <DetailsSection>
        <DetailsSectionTitle>Night Roles</DetailsSectionTitle>
        <DetailsFieldGrid>
          <DetailsField>
            <MetadataFieldLabel>Host</MetadataFieldLabel>
            <MetadataFormControl>
              <StyledSelect
                MenuProps={dropdownMenuProps}
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
          </DetailsField>
          <DetailsField>
            <MetadataFieldLabel>Scorekeeper</MetadataFieldLabel>
            <MetadataFormControl>
              <StyledSelect
                MenuProps={dropdownMenuProps}
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
          </DetailsField>
          <DetailsField>
            <MetadataFieldLabel>Tiebreak Winner</MetadataFieldLabel>
            <StyledButton type="button" onClick={openTiebreakDialog} style={{ width: '100%', margin: 0 }}>
              {tiebreakWinner ? tiebreakWinner : 'Set Tiebreak Winner'}
            </StyledButton>
          </DetailsField>
        </DetailsFieldGrid>
      </DetailsSection>

      <DetailsSection>
        <DetailsSectionTitle>Style Points</DetailsSectionTitle>
        <StylePointsGrid>
          {playerNamesDisplay.map((name) => (
            <StylePointRow key={name}>
              <StylePointName>{name}</StylePointName>
              <DetailTextField
                value={stylePoints?.[name] ?? ''}
                onChange={(e) => {
                  setStylePoints((prev) => setStylePointValue(prev, name, e.target.value));
                  markDirty();
                }}
                type="number"
                inputProps={{ step: 0.5, min: 0 }}
              />
            </StylePointRow>
          ))}
        </StylePointsGrid>
      </DetailsSection>
    </DetailsPanel>
  );

  return (
    <>
    <GlobalStyle />
    <StyledTableContainer>
      <Grid container alignItems="center" rowSpacing={1} columnSpacing={0} sx={{ width: '100%', margin: 0 }}>

        {/* Left Section */}
        <Grid item xs={12} md={isCompactScreen ? 12 : 4} sx={{ minWidth: 0 }}>
          <Box
          display="flex"
          alignItems="center"
          justifyContent={isMobileView ? 'center' : 'flex-start'}
          flexDirection="row"
          flexWrap={isMobileView ? 'wrap' : 'nowrap'}
          gap={isMobileView ? 0.65 : 0}
          padding={isMobileView ? '0.28rem 0.35rem 0.15rem' : '0.2rem'}
          maxWidth={isMobileView ? '72rem' : 'none'}
          minWidth={0}
          margin={isMobileView ? '0 auto' : '0'}
          marginLeft={isMobileView ? '0' : '0.2rem'}>
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
            {!isMobileView && roundNavigationControls}

            <CompactTopControlGroup>
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
                  margin: isCompactScreen ? 0 : '0.4rem',
                  marginLeft: isCompactScreen ? '0' : '1rem',
                  width: isCompactScreen ? (isSmallScreen ? '11rem' : 'min(100%, 15rem)') : undefined,
                  maxWidth: isCompactScreen ? (isSmallScreen ? '11rem' : '15rem') : undefined,
                }}
              />

              <StyledButton variant="contained" color="secondary" onClick={handleAddPlayer}>
                Add
              </StyledButton>
            </CompactTopControlGroup>
          </Box>
        </Grid>

        {/* Right Section */}
        <Grid item xs={12} md={isCompactScreen ? 12 : 8} sx={{ minWidth: 0 }}>
          <Box
            display="flex"
            justifyContent={isCompactScreen ? 'center' : 'flex-end'}
            alignItems="center"
            flexDirection="row"
            flexWrap="wrap"
            gap={isCompactScreen ? 0.65 : 0}
            padding={isCompactScreen ? '0 0.35rem 0.24rem' : 0}
            maxWidth={isCompactScreen ? '72rem' : 'none'}
            minWidth={0}
            margin={isCompactScreen ? '0 auto' : 0}
          >
            <StyledButton variant="contained" color="secondary" onClick={() => setIsBottomRowVisible(prevState => !prevState)}>
              Toggle Details
            </StyledButton>
            <StyledButton variant="contained" color="secondary" onClick={() => handleAddColumn(selectedDate, rounds.length + 1)}>
              Add Round
            </StyledButton>
            {isMobileView && roundNavigationControls}

            {!isCompactScreen && (
              <StyledButton variant="contained" color="primary" onClick={saveData} style={{ backgroundColor: isSaved ? '#1e7662' : '#810e19' }}>
                Save Scoresheet
              </StyledButton>
            )}

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
            <StyledTableCell sx={{color:'var(--scoresheet-text, #fff)'}}><div>Joker Bonus</div></StyledTableCell>
            <StyledTableCell sx={{color:'var(--scoresheet-text, #fff)'}}><div>Creator Bonus</div></StyledTableCell>
              <StyledTableCell sx={{color:'var(--scoresheet-text, #fff)'}} onClick={() => setIsSortAscending(!isSortAscending)}><div>Total</div></StyledTableCell>
                     <StyledTableCell sx={{color:'var(--scoresheet-text, #fff)', marginX:"0px", padding:"0"}}><div></div></StyledTableCell>

          </TableRow>
        </TableHead>
        <TableBody>
          {sortedPlayersForDisplay.map((player) => {
              const stylePointTheme = getStylePointTheme(stylePoints, player);
              const activeJokerRouletteTitle = jokerRouletteHighlights[player];
              const isJokerRouletteSpinning = Boolean(jokerRouletteSpinningPlayers[player]);
              const playerDisplayName = getDisplayNameForPlayerField(player);
              const playerIconUrl = getPlayerIconUrl(playerIconMap, player);
              return (<TableRow key={player}>
                  <StyledTableCell player={player}>
                          <PlayerNameStack>
                          <PlayerNameAnchor>
                              <PlayerNameLabel>
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
                                      href={url + `/player_profile/${playerDisplayName}/`}
                                      className="player_name"
                                      data-player={playerDisplayName}
                                      data-player-field={player}
                                  >
                                      {playerDisplayName}
                                  </a>
                              </PlayerNameLabel>
                              {playerIconUrl && (
                                  <PlayerAvatarIcon
                                      src={playerIconUrl}
                                      alt={`${playerDisplayName} icon`}
                                  />
                              )}
                          </PlayerNameAnchor>
                      </PlayerNameStack>
                  </StyledTableCell>
                  <StyledTableCell sx={{maxWidth: '200px'}} className={selectedColumnIndex === 1 ? 'selected-column' : ''}>
                      <JokerFormControl>
                          <InputLabel id="demo-simple-select-label"></InputLabel>
                          <JokerSelect
                              MenuProps={dropdownMenuProps}
                              labelId="demo-simple-select-label"
                              id="demo-simple-select"
                              displayEmpty
                              value={isJokerRouletteSpinning ? JOKER_RANDOMIZE_VALUE : getPrimaryJokerRoundForPlayer(player)}
                              renderValue={(value) => {
                                if (value === JOKER_RANDOMIZE_VALUE) {
                                  return <span style={{ color: '#f6c343', fontWeight: 700 }}>Randomizing...</span>;
                                }
                                return getDisplayedJokerSelectionLabel(player);
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
                          </JokerSelect>
                      </JokerFormControl>
                  </StyledTableCell>
                  {rounds.map((round, index) => (
                      (() => {
                        const jokerRoundsForPlayer = getSelectedJokerRoundsForPlayer(player);
                        const isDoubleJoker = jokerRoundsForPlayer.length > 1;
                        const isJokerCell = !isJokerRouletteSpinning && jokerRoundsForPlayer.includes(round.title);
                        const isCreatorCell = roundIncludesCreator(round.title, playerDisplayName, round);
                        const scoreCellClassName = [
                          index + 2 === selectedColumnIndex ? 'selected-column' : '',
                          (isJokerCell || isCreatorCell) ? 'star-ricochet' : '',
                        ].filter(Boolean).join(' ');

                        return (
                      <StyledTableCell
                           sx={{color:textColor}}
                           className={scoreCellClassName}
                          key={index}
                          contentEditable
                          style={{
                              backgroundColor:
                                  activeJokerRouletteTitle === round.title
                                      ? '#f3bc34'
                                      : isJokerCell
                                      ? (isDoubleJoker ? 'rgba(30, 118, 98, 0.6)' : '#1e7662')
                                      : isCreatorCell
                                          ? '#810e19'
                                          : 'var(--scoresheet-surface, #333)',
                              color: 'var(--scoresheet-text, #fff)',
                              fontFamily: 'Monaco',
                                fontSize: "1rem",
                          }}
                          onContextMenu={(event) => handleScoreCellContextMenu(event, player, round.title)}
                          onTouchStart={(event) => handleScoreCellTouchStart(event, player, round.title)}
                          onTouchEnd={clearScoreCellLongPress}
                          onTouchMove={clearScoreCellLongPress}
                          onTouchCancel={clearScoreCellLongPress}
                          onBlur={(event) => handleScoreChange(event, player, round.title, round)}
                      >
                          {getDisplayedRoundScore(scores, player, round)}
                      </StyledTableCell>
                        );
                      })()
                  ))}
                  <StyledTableCell>
                  <div className={"textCell"}>
                    {getDisplayedJokerBonus(rounds, scores, player, selectedRounds[player], medianScores)}
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
                    <CoopRowToggleLabel
                      control={
                        <Checkbox
                          className="star-ricochet"
                          checked={cooperativeStatus[round.title] || false}
                          onChange={(event) => handleCooperativeChange(round.title, event.target.checked)}
                        />
                      }
                      label="Co-op"
                    />
                    </StyledTableCell>
                    ))}

            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}
            <TableCell></TableCell> {/* Empty cell for the player column */}
            <TableCell></TableCell> {/* Empty cell for the joker column */}

          </StyledTableRow>
        {isBottomRowVisible && !isCompactScreen && (
          <StyledTableRow>
            <DetailsPanelCell colSpan={rounds.length + 6}>
              {detailsPanelContent}
            </DetailsPanelCell>
          </StyledTableRow>
        )}
        </TableBody>
      </StyledTable>
      {isBottomRowVisible && isCompactScreen && (
        <MobileDetailsPanelShell>
          {detailsPanelContent}
        </MobileDetailsPanelShell>
      )}
      <MetadataSection>
        <MetadataGrid>
          <MetadataActionField>
            <MetadataActionRow>
              <MetadataActionButtons>
                <StyledButton type="button" onClick={handleCrownWinnerClick}>
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
              rows={isCompactScreen ? 1 : 2}
              placeholder="Enter Nightly Notes"
            />
          </MetadataNotesFieldWrapper>
        </MetadataGrid>
      </MetadataSection>
      <Menu
        open={scoreCellMenu.mouseY !== null}
        onClose={closeScoreCellMenu}
        anchorReference="anchorPosition"
        anchorPosition={
          scoreCellMenu.mouseY !== null && scoreCellMenu.mouseX !== null
            ? { top: scoreCellMenu.mouseY, left: scoreCellMenu.mouseX }
            : undefined
        }
        PaperProps={{
          sx: {
            backgroundColor: 'var(--scoresheet-menu-bg, #333)',
            color: 'var(--scoresheet-text, #fff)',
            borderRadius: 0,
            border: '1px solid #1e7662',
            boxShadow: '0 16px 36px rgba(0, 0, 0, 0.45)',
            fontFamily: 'Monaco, monospace',
            '& .MuiMenuItem-root': {
              fontFamily: 'Monaco, monospace',
              fontSize: '0.95rem',
            },
            '& .MuiMenuItem-root.Mui-disabled': {
              opacity: 0.78,
              color: 'var(--scoresheet-text-muted, rgba(255,255,255,0.8))',
            },
            '& .MuiMenuItem-root:hover': {
              backgroundColor: 'var(--scoresheet-menu-hover, rgba(30, 118, 98, 0.22))',
            },
          },
        }}
      >
        <MenuItem disabled>
          {scoreCellMenu.playerDisplayName && scoreCellMenu.roundTitle
            ? `${scoreCellMenu.playerDisplayName} • ${scoreCellMenu.roundTitle}`
            : 'Cell actions'}
        </MenuItem>
        <MenuItem onClick={handleSetCellAsJoker}>{scoreCellJokerMenuLabel}</MenuItem>
        <MenuItem onClick={handleSetCellAsCreator}>Set as Creator</MenuItem>
      </Menu>
      <Dialog
        open={isStylePointDialogOpen}
        onClose={() => setIsStylePointDialogOpen(false)}
        fullWidth
        maxWidth="xs"
        PaperProps={{
          sx: {
            backgroundColor: 'var(--scoresheet-menu-bg, #333)',
            color: 'var(--scoresheet-text, #fff)',
            borderRadius: 0,
            border: '1px solid #1e7662',
            boxShadow: '0 16px 36px rgba(0, 0, 0, 0.45)',
          },
        }}
      >
        <DialogTitle sx={{ fontFamily: 'Monaco, monospace', color: 'var(--scoresheet-text, #fff)' }}>Award Style Point</DialogTitle>
        <DialogContent sx={{ color: 'var(--scoresheet-text, #fff)' }}>
          <Box sx={{ pt: 1 }}>
            <FormControl
              fullWidth
              sx={{
                '& .MuiInputLabel-root': { color: 'var(--scoresheet-text-muted, rgba(255,255,255,0.72))', fontFamily: 'Monaco, monospace' },
                '& .MuiInputLabel-root.Mui-focused': { color: 'var(--scoresheet-text, #fff)' },
                '& .MuiOutlinedInput-root': {
                  backgroundColor: 'var(--scoresheet-surface, #333)',
                  color: 'var(--scoresheet-text, #fff)',
                  fontFamily: 'Monaco, monospace',
                },
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#1e7662',
                },
                '& .MuiSvgIcon-root': { color: 'var(--scoresheet-text, #fff)' },
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
                      backgroundColor: 'var(--scoresheet-menu-bg, #333)',
                      color: 'var(--scoresheet-text, #fff)',
                      border: '1px solid #1e7662',
                      '& .MuiMenuItem-root': {
                        fontFamily: 'Monaco, monospace',
                      },
                      '& .MuiMenuItem-root.Mui-selected': {
                        backgroundColor: '#1e7662',
                      },
                      '& .MuiMenuItem-root:hover': {
                        backgroundColor: 'var(--scoresheet-menu-hover, #185e4f)',
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
            backgroundColor: 'var(--scoresheet-menu-bg, #333)',
            color: 'var(--scoresheet-text, #fff)',
            borderRadius: 0,
            border: '1px solid #1e7662',
            boxShadow: '0 16px 36px rgba(0, 0, 0, 0.45)',
          },
        }}
      >
        <DialogTitle sx={{ fontFamily: 'Monaco, monospace', color: 'var(--scoresheet-text, #fff)' }}>Set Tiebreak Winner</DialogTitle>
        <DialogContent sx={{ color: 'var(--scoresheet-text, #fff)' }}>
          <Box sx={{ pt: 1 }}>
            <FormControl
              fullWidth
              sx={{
                '& .MuiInputLabel-root': { color: 'var(--scoresheet-text-muted, rgba(255,255,255,0.72))', fontFamily: 'Monaco, monospace' },
                '& .MuiInputLabel-root.Mui-focused': { color: 'var(--scoresheet-text, #fff)' },
                '& .MuiOutlinedInput-root': {
                  backgroundColor: 'var(--scoresheet-surface, #333)',
                  color: 'var(--scoresheet-text, #fff)',
                  fontFamily: 'Monaco, monospace',
                },
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#1e7662',
                },
                '& .MuiSvgIcon-root': { color: 'var(--scoresheet-text, #fff)' },
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
                      backgroundColor: 'var(--scoresheet-menu-bg, #333)',
                      color: 'var(--scoresheet-text, #fff)',
                      border: '1px solid #1e7662',
                      '& .MuiMenuItem-root': {
                        fontFamily: 'Monaco, monospace',
                      },
                      '& .MuiMenuItem-root.Mui-selected': {
                        backgroundColor: '#1e7662',
                      },
                      '& .MuiMenuItem-root:hover': {
                        backgroundColor: 'var(--scoresheet-menu-hover, #185e4f)',
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
