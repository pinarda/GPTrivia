import React, { useEffect, useState, useMemo, useRef } from "react";
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
} from "@mui/material";
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import styled, { createGlobalStyle } from 'styled-components';


    const playerColorMapping = {
        'score_alex': '#D2042D',
        'score_ichigo': '#ff7f0e',
        'score_megan': '#8e4585',
        'score_zach': '#A020F0',
        'score_jenny': '#ffef00',
        'score_debi': '#8551ff',
        'score_mom': '#8551ff',
        'score_dan': '#0000FF',
        'score_dad': '#0000FF',
        'score_chris': '#005427',
        'score_drew': '#8c564b',
        'score_jeff': '#333333',
        'score_paige': '#333333',
        'score_dillon': '#333333',
        'unknown': '#333333',
    };

    const XButton = styled.div`
      width: 20px; // Set the width
      height: 20px; // Set the height
      background-color: ${props => playerColorMapping[props.player] || '#000'}; // Dynamic background color
      color: ${props => playerTextColor(playerColorMapping[props.player] || '#000000')};  // Set the text color, depending on the background color brightness
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      
      &:hover {
        background-color: ${props => darkenBackground(playerColorMapping[props.player] || '#000')};// Darken the background color on hover
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
      const brightness = r + g + b;
      if(brightness < 480) {
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
          color: ${props => playerColorMapping[props.player] || '#000'};
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
        background-color: #333;
        color: #fff;
      
        && * {
            font-size: 0.8rem;
            font-family: "Monaco";
            color: #fff;
          margin: 0;
          padding: 0.15rem;
        }
      
      .textCell {
        color: #fff;
        text-align: center;
        font-family: "Monaco";
        margin: 0;
      }
    `;

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

      const GlobalStyle = createGlobalStyle`
          .MuiPopover-root .MuiPaper-root {
            display: block;
          }
    `;



const PlayerTable = () => {
    const defaultPlayers = useMemo(() => {
      // The initial calculation of defaultPlayers goes here
      return ["score_alex", "score_dan", "score_debi", "score_jenny", "score_megan", "score_ichigo", "score_chris", "score_zach"];
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
    const [selectedColumnIndex, setSelectedColumnIndex] = useState(1);
    const [updateFlag, setUpdateFlag] = useState(0); // Update flag
    const isLocalUpdate = useRef(false);
    const [pageLoadFlag, setPageLoadFlag] = useState(0); // Page load flag

    const theme = useTheme();
    const isSmallScreen = useMediaQuery(theme.breakpoints.down('sm'));

    // let url = "http://localhost:8000"
    let url = "https://hailsciencetrivia.com"

    const wsRef = useRef(null);

    function sortPlayers(b, a) {
      const totalScoreA = rounds.reduce((total, round) => total + (round[a] || 0), 0) + (
                                                                                    rounds.filter(round => {
                                                                                          const playerName = a.replace('score_', '').charAt(0).toUpperCase() + a.replace('score_', '').slice(1);
                                                                                              if (playerName === "Dan") {
                                                                                                return round.creator === "Dad" || round.creator === "Dan";
                                                                                              } else if (playerName === 'Debi') {
                                                                                                return round.creator === 'Mom' || round.creator === 'Debi';
                                                                                              } else {
                                                                                                return round.creator === playerName;
                                                                                              }
                                                                                            })
                                                                                        .map(round => {
                                                                                            if (selectedRounds[a] != round.title) {
                                                                                                return medianScores[rounds.indexOf(round)];
                                                                                            }
                                                                                            return 0;
                                                                                        })
                                                                                        .reduce((acc, score) => acc + (score || 0), 0)
                                                                                      ) + (scores[a] && scores[a][selectedRounds[a]] ? scores[a][selectedRounds[a]] : 0);
      const totalScoreB = rounds.reduce((total, round) => total + (round[b] || 0), 0) + (
                                                                                    rounds.filter(round => {
                                                                                          const playerName = b.replace('score_', '').charAt(0).toUpperCase() + b.replace('score_', '').slice(1);
                                                                                              if (playerName === "Dan") {
                                                                                                return round.creator === "Dad" || round.creator === "Dan";
                                                                                              } else if (playerName === 'Debi') {
                                                                                                return round.creator === 'Mom' || round.creator === 'Debi';
                                                                                              } else {
                                                                                                return round.creator === playerName;
                                                                                              }
                                                                                            })
                                                                                        .map(round => {
                                                                                            if (selectedRounds[b] != round.title) {
                                                                                                return medianScores[rounds.indexOf(round)];
                                                                                            }
                                                                                            return 0;
                                                                                        })
                                                                                        .reduce((acc, score) => acc + (score || 0), 0)
                                                                                      ) + (scores[b] && scores[b][selectedRounds[b]] ? scores[b][selectedRounds[b]] : 0);

      return isSortAscending ? totalScoreA - totalScoreB : totalScoreB - totalScoreA;
    }

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
        } else {
          return '0.8rem'; // Even smaller font size for text length 20 and above
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
      setPageLoadFlag(prev => prev - 1);
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
            const allPlayers = json.map(item => item.creator);
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
          setRounds(json);

          // set tempTitles if it hasn't been set yet
            if (tempTitles.length === 0) {
                let initialTempTitles = [];
                json.forEach(round => {
                    initialTempTitles.push(round.title);
                });
                setTempTitles(initialTempTitles);
            }


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
          let playerNames = [...defaultPlayers];
          for (let round of json) {
            for (let key of Object.keys(round)) {
              if (key.startsWith('score_') && round[key] !== 0 && round[key] !== null) {
                playerNames.push(key);
              }
            }
          }


          // Get unique player names
          playerNames = [...new Set(playerNames)];
          setPlayers(playerNames);

          const initialScores = {};
          playerNames.forEach(player => {
            initialScores[player] = {};
            json.forEach(round => {
              initialScores[player][round.title] = round[player];
            });
          });
          setScores(initialScores);
        })
        .catch(function() {
            //setErrorMessage("Failed to fetch rounds");
        });
      setPageLoadFlag(prev => prev + 1);
    }, [selectedDate, defaultPlayers, dates.length, tempTitles.length, url, updateFlag]);

    useEffect(() => {
        setPageLoadFlag(prev => prev - 1);
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
            // strip the score_ prefix from the player names
            const playerNames = players.map(player => player.replace('score_', ''));
            const selectedPresentation = json.find(presentation => convertDate(presentation.name) === selectedDate);


            if(selectedPresentation) {
                const jokerRoundIndicesString = selectedPresentation.joker_round_indices;
                const jokerRoundIndices = JSON.parse(jokerRoundIndicesString.replace(/'/g, "\"").replace(/^'/, '"').replace(/'$/, '"').replace(/~~~~/g, "'"));
                // const jokerRoundIndices = selectedPresentation.joker_round_indices;
                const ID = selectedPresentation.presentation_id;

                setPresID(ID);

                const newJokerRounds = playerNames.reduce((acc, player) => {
                    // remember to lower case the player name
                    if (jokerRoundIndices[player]) {
                        acc[player] = jokerRoundIndices[player];
                    }
                    return acc;
                }, {});

                const initialSelectedRounds = playerNames.reduce((acc, curr) => {
                    acc[curr] = newJokerRounds[curr] || "Select";
                    return acc;
                }, {});

                //add score_ prefix back to the player names
                const initialSelectedRoundsWithPrefix = {};
                for (let key in initialSelectedRounds) {
                    if(initialSelectedRounds[key] !== "Select")
                        initialSelectedRoundsWithPrefix['score_' + key] = initialSelectedRounds[key];
                }

                setSelectedRounds(initialSelectedRoundsWithPrefix);
            } else {
                console.log("No presentation found for date: ", selectedDate);
                setSelectedRounds(playerNames.reduce((acc, curr) => ({...acc, [curr]: "Select"}), {}));
                setPresID(0);
            }
        })
        .catch(error => {
            console.error('Error fetching presentations:', error);
        });
        setPageLoadFlag(prev => prev + 1);
    }, [selectedDate, players, url, updateFlag]);

    useEffect(() => {
      if (players.length > 0 && rounds.length > 0) {

        // Compute median scores
        const medianScores = rounds.map(round => {
            const transformedCreatorName = transformName(round.creator);
            const formattedName = `score_${transformedCreatorName.charAt(0).toLowerCase() + transformedCreatorName.slice(1)}`;
            if (players.includes(formattedName)) {
                const scores = Object.keys(round)
                  .filter(key => key.startsWith('score_') && typeof round[key] === 'number' && formattedName !== key)
                  .map(scoreKey => round[scoreKey]);

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
        wsRef.current = new WebSocket('wss://hailsciencetrivia.com/ws/scoresheet/');

        wsRef.current.onopen = () => {
            console.log('Connected to the WebSocket');
        };

        wsRef.current.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data.message)

            console.log ('isLocalUpdate value at ', new Date().toLocaleTimeString(), ': ', isLocalUpdate.current);
            if (data.message && data.message.action === 'update' && !isLocalUpdate.current) {
                console.log('Received update message')
                setUpdateFlag(prev => prev + 1); // Increment the flag to trigger re-fetch
                console.log('Update flag incremented to: ', updateFlag)
            }
        };

        wsRef.current.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        wsRef.current.onclose = () => {
            console.log('Disconnected from the WebSocket');
        };

        // Cleanup function for WebSocket
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, []);

    const handleScoreChange = (event, player, roundTitle, round) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;

        const inputValue = event.target.innerText;
        let newScore;
        setIsSaved(false);

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
    };


    const handleRemovePlayer = (playerToRemove) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;

      setPlayers(players.filter(player => player !== playerToRemove));
    };

    const handleChangeDate = (eventOrDate) => {

        setPageLoadFlag(prevState => prevState - 1);
        if (!isSaved) {
            const confirmChange = window.confirm("Are you sure you want to change the date? You have unsaved changes.");
            if (!confirmChange) return;
        }

        if (eventOrDate instanceof Event) {
            setSelectedDate(eventOrDate.target.value);
            const filteredRounds = rounds.filter(round => round.date === eventOrDate.target.value);
            setRounds(filteredRounds);
            let initialTempTitles = [];
            filteredRounds.forEach(round => {
                initialTempTitles.push(round.title);
            });
            setTempTitles(initialTempTitles);
        } else {
            // if the currently selected date is already today, don't do anything
            let currentDateString = selectedDate;
            let currentDate = new Date(currentDateString);
            const today = new Date();
            const year = today.getFullYear();
            const month = today.getMonth() + 1;
            const day = today.getDate();
            if (currentDate.getFullYear() === year && currentDate.getMonth() + 1 === month && currentDate.getDate() + 1 === day) {
                return;
            }
            // remember to pad the month and day with leading zeros (they must be converted to strings first)
            const todayStr = `${year}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`;
            setDates(prevDates => [...prevDates, todayStr]);
            setSelectedDate(todayStr);
            setTempTitles([]);
            setPresID(0);
        }
        setPageLoadFlag(prevState => prevState + 1);
    }

    const confirmPastChange = () => {
        let currentDateString = selectedDate;
        let currentDate = new Date(currentDateString);
        const today = new Date();
        const year = today.getFullYear();
        const month = today.getMonth() + 1;
        const day = today.getDate();
        let confirmChange = true;
        if (currentDate.getFullYear() != year || currentDate.getMonth() + 1 != month || currentDate.getDate() + 1 != day) {
            confirmChange = window.confirm("Are you sure you want to edit the scoresheet for a previous date?");
        }
        return confirmChange;
    }

    const handleRoundTitleChange = (index, newTitle) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;

      const oldTitle = rounds[index].title;

      setIsSaved(false);


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

    };

    const handleAddPlayer = () => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;

      if (newPlayerName.trim()) {
        const formattedName = `score_${newPlayerName.trim().toLowerCase()}`;
        if (!players.includes(formattedName)) {
          setPlayers([...players, formattedName]);
          setNewPlayerName('');
        } else {
          alert('Player name already exists!');
        }
      }
      setIsSaved(false);
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
      setIsSaved(false);
    };

    const handleMinor1CategoryChange = (roundTitle, newValue) => {
        setSelectedMinor1Categories(prevState => ({
            ...prevState,
            [roundTitle]: newValue,
        }));
      setIsSaved(false);
    };

    const handleMinor2CategoryChange = (roundTitle, newValue) => {
        setSelectedMinor2Categories(prevState => ({
            ...prevState,
            [roundTitle]: newValue,
        }));
      setIsSaved(false);
    };

    const handleCooperativeChange = (roundTitle, isChecked) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;
      setCooperativeStatus(prevState => ({
        ...prevState,
        [roundTitle]: isChecked,
      }));
      setIsSaved(false);
    };

    const handleReplayChange = (roundTitle, isChecked) => {
        setIsReplay(prevState => ({
            ...prevState,
            [roundTitle]: isChecked,
        }));
      setIsSaved(false);
    };

    useEffect(() => {
        console.log('roundCreators changed', roundCreators);
      }, [roundCreators]);

      useEffect(() => {
        console.log('rounds changed', rounds);
      }, [rounds]);

    const handleMaxScoreChange = (roundTitle, newMaxScore) => {
                setMaxScores(prevScores => ({
            ...prevScores,
            [roundTitle]: newMaxScore
        }));
    };

    useEffect(() => {
        if (pageLoadFlag >= 0) {
            console.log('scoresheet changed, saving...');
            saveData();
        }
    }, [selectedRounds, rounds, roundCreators, selectedMajorCategories, selectedMinor1Categories, selectedMinor2Categories, isReplay, maxScores, cooperativeStatus]);


    const handleCreatorChange = (roundTitle, newCreatorName) => {
      setRoundCreators(prevRoundCreators => ({
        ...prevRoundCreators,
        [roundTitle]: newCreatorName,
      }));

      setIsSaved(false);

      setScores(prevScores => {
        const newScores = { ...prevScores };
        const transformedCreatorName = transformName(newCreatorName);
        const formattedName = `score_${transformedCreatorName.charAt(0).toLowerCase() + transformedCreatorName.slice(1)}`;

        // Iterate over rounds and remove the new creator's score from the respective round
          if (formattedName in players) {
            newScores[formattedName][roundTitle] = null;
        }

        return newScores;
      });

      //call setRounds to trigger the useEffect to recompute medians
        setRounds(prevRounds => {
            const newRounds = [...prevRounds];
            const roundIndex = newRounds.findIndex(round => round.title === roundTitle);
            if (roundIndex !== -1) {
                newRounds[roundIndex].creator = newCreatorName;
                newRounds[roundIndex][`score_${newCreatorName.charAt(0).toLowerCase() + newCreatorName.slice(1)}`] = null;
            }
            return newRounds;
        });
    };

    const saveData = () => {
        const formattedRoundsData = rounds.map((round, index) => formatRoundData(round, index));
        // replace keys in selectedRounds by removing the score_ prefix and capitalizing the first letter
        const formattedSelectedRounds = {};
        for (let key in selectedRounds) {
            formattedSelectedRounds[key.replace('score_', '').charAt(0).toLowerCase() + key.replace('score_', '').slice(1)] = selectedRounds[key];
        }
        // put each round name into an array and pass it to the backend, and do the same for round creators
        const roundNames = [];
        const roundCreators = [];
        for (let round in formattedRoundsData) {
            roundNames.push(formattedRoundsData[round]["title"]);
            roundCreators.push(formattedRoundsData[round]["creator"]);
        }

        const payload = {
            rounds: formattedRoundsData,
            joker_round_indices: formattedSelectedRounds,  // Add appropriate data here
            presentation_id: presID,  // Add appropriate data here
            round_names: roundNames,
            round_creators: roundCreators,
        };

        fetch(url + '/save_scores/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken,  // Add the CSRF token here
              'Authorization': `Token ${localStorage.getItem('token')}`,
            },
            body: JSON.stringify(payload),
        })
        .then(response => response.json())
        .then(data => {
          console.log('Success:', data);
        })
        .catch((error) => {
          console.error('Error:', error);
        });




        setIsSaved(true);
    };

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

        fetch(url + `/create_round/${date}/${number}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'Authorization': `Token ${localStorage.getItem('token')}`,
            },
        })
        .then(response => response.json())
        .then(data => {
            console.log('New Round Created:', data);
            setRounds(prevRounds => [...prevRounds, data]);
            setTempTitles(prevTitles => [...prevTitles, data.title]);
        })
        .catch((error) => {
            console.error('Error:', error);
        });

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            console.log('Sending update message to WebSocket via React');
            isLocalUpdate.current = true;
            console.log ('isLocalUpdate set to true at ', new Date().toLocaleTimeString());
            wsRef.current.send(JSON.stringify({type: 'scoresheet_message', message: {'action': 'update'}}));
            setTimeout(() => isLocalUpdate.current = false, 10000); // Reset flag after a short delay
        } else {
            console.log('WebSocket is not open. Current state:', wsRef.current.readyState);
        }
    }

    const handleTempTitleChange = (index, newTitle) => {
        setTempTitles(prevTitles => {
            const newTitles = [...prevTitles];
            newTitles[index] = newTitle;
            return newTitles;
        });
    }

    const handleRemoveColumn = (roundId) => {
        const confirmChange = confirmPastChange()
        if (!confirmChange) return;
        const confirmDelete = window.confirm("Are you sure you want to delete this round? This action cannot be undone.");
        if (!confirmDelete) return;

        fetch(url + `/delete_round/${roundId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': csrfToken,
              'Authorization': `Token ${localStorage.getItem('token')}`,
            },
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
        })
        .catch((error) => {
          console.error('Error:', error);
        });

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            console.log('Sending update message to WebSocket via React');
            isLocalUpdate.current = true;
            console.log ('isLocalUpdate set to true at ', new Date().toLocaleTimeString());
            wsRef.current.send(JSON.stringify({type: 'scoresheet_message', message: {'action': 'update'}}));
            setTimeout(() => isLocalUpdate.current = false, 10000); // Reset flag after a short delay
        } else {
            console.log('WebSocket is not open. Current state:', wsRef.current.readyState);
        }
    };






  return (
    <>
    <GlobalStyle />
    <StyledTableContainer>
      <Grid container alignItems="center" spacing={1}>

        {/* Left Section */}
        <Grid item xs={4}>
          <Box
          display="flex"
          alignItems="center"
          justifyContent = "flex-start"
          flexDirection={isSmallScreen ? 'column' : 'row'}
          padding={isSmallScreen ? '0.4rem' : '0.2rem'}
          marginLeft={isSmallScreen ? '0.4rem' : '0.2rem'}>
            <StyledFormControl>
              <Select
                value={selectedDate}
                onChange={(event) => handleChangeDate(event)}
              >
                {sortedDates.map((date, index) => (
                  <MenuItem key={index} value={date}>{date}</MenuItem>
                ))}
              </Select>
                <StyledButton variant="contained" color="secondary" onClick={() => handleChangeDate()}>
                    Today
                </StyledButton>
            </StyledFormControl>

            <StyledTextField
              value={newPlayerName}
              onChange={(e) => setNewPlayerName(e.target.value)}
              variant="outlined"
              placeholder="Enter player"
            style={{ margin: "0.4rem" }}
            />

            <StyledButton variant="contained" color="secondary" onClick={() => handleAddPlayer(prevState => !prevState)}>
              +
            </StyledButton>
              <StyledFormControl>
                <StyledInputLabel className={"showonsmall"}>Round</StyledInputLabel>
                  <StyledSelect
                    className={"showonsmall"}
                    value={selectedColumnIndex.toString()}
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
        <Grid item xs={8}>
          <Box display="flex" justifyContent="flex-end" alignItems="center"  flexDirection={isSmallScreen ? 'column' : 'row'}>
            <StyledButton variant="contained" color="secondary" onClick={() => setIsBottomRowVisible(prevState => !prevState)}>
              Toggle Details
            </StyledButton>
            <StyledButton variant="contained" color="secondary" onClick={() => handleAddColumn(selectedDate, rounds.length + 1)}>
              Add Round
            </StyledButton>
            <StyledButton variant="contained" color="primary" onClick={saveData} style={{ backgroundColor: isSaved ? '#1e7662' : '#810e19' }}>
              Save Scoresheet
            </StyledButton>
          </Box>
        </Grid>

      </Grid>
      <StyledTable id="table">
        <TableHead>
          <TableRow>
            <StyledTableCell><div className={"textCell"}>Player</div></StyledTableCell>
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
          {[...players].sort(sortPlayers).map((player) => {
              return (<TableRow key={player}>
                  <StyledTableCell player={player}>
                      <a
                          href={url + `/player_profile/${player.replace('score_', '')}/`}
                          className="player_name"
                          data-player={player.replace('score_', '')}
                      >
                          {player.replace('score_', '').charAt(0).toUpperCase() + player.replace('score_', '').slice(1)}
                      </a>
                  </StyledTableCell>
                  <StyledTableCell sx={{maxWidth: '200px'}} className={selectedColumnIndex === 1 ? 'selected-column' : ''}>
                      <StyledFormControl>
                          <InputLabel id="demo-simple-select-label"></InputLabel>
                          <Select sx={{maxWidth: '150px'}}
                              labelId="demo-simple-select-label"
                              id="demo-simple-select"
                              value={selectedRounds[player] || "Select"} // Access the selected round for this player
                              onChange={(event) => {
                                // Update the selected round for this player
                                  if (!confirmPastChange()) return;                                        // Set the saved status to false
                                setIsSaved(false);
                                setSelectedRounds({
                                    ...selectedRounds,
                                    [player]: event.target.value
                                });
                            }} // Update the selected round for this player
                          >
                              <MenuItem value={"Select"}>- Select -</MenuItem>
                              {rounds.map((round, index) => (
                                  <MenuItem value={round.title} key={index}>{round.title}</MenuItem>
                              ))}
                          </Select>
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
                                  selectedRounds[player] === round.title
                                      ? '#1e7662'
                                      : roundCreators[round.title] === player.replace('score_', '').charAt(0).toUpperCase() + player.replace('score_', '').slice(1)
                                          ? '#810e19'
                                          : '#333',
                              color: 'white',
                              fontFamily: 'Monaco',
                                fontSize: "1rem",
                          }}
                          onBlur={(event) => handleScoreChange(event, player, round.title, round)}
                      >
                          {(() => {
                                const cellValue = scores[player] && scores[player][round.title]
                                                  ? scores[player][round.title]
                                                  : round[player];

                                return (typeof cellValue === 'number')
                                       ? parseFloat(cellValue.toFixed(2))
                                       : cellValue;
                            })()}
                      </StyledTableCell>
                  ))}
                  <StyledTableCell>
                  <div className={"textCell"}>
                    {(() => {
                      const roundScore = scores[player] && scores[player][selectedRounds[player]];
                      return (typeof roundScore === 'number') ? parseFloat(roundScore.toFixed(2)) : roundScore;
                    })()}
                  </div>
                </StyledTableCell>
                  <StyledTableCell><div className={"textCell"}>{(() => {
                      const playerName = player.replace('score_', '').charAt(0).toUpperCase() + player.replace('score_', '').slice(1);

                      const total = rounds
                        .filter(round => {
                          if (playerName === "Dan") {
                            return round.creator === "Dad" || round.creator === "Dan";
                          } else if (playerName === 'Debi') {
                            return round.creator === 'Mom' || round.creator === 'Debi';
                          } else {
                            return round.creator === playerName;
                          }
                        })
                        .map(round => {
                            if (selectedRounds[player] != round.title) {
                                return medianScores[rounds.indexOf(round)];
                            }
                            return 0;
                        })
                        .reduce((acc, score) => acc + (score || 0), 0);

                      return (typeof total === 'number') ? parseFloat(total.toFixed(2)) : total;

                    })()}
                  </div></StyledTableCell>

                  <StyledTableCell>
                      <div className={"textCell"}>
                        {(() => {
                          const playerName = player.replace('score_', '').charAt(0).toUpperCase() + player.replace('score_', '').slice(1);

                          const roundTotal = rounds.reduce((total, round) => total + (round[player] || 0), 0);

                          const creatorBonus = rounds
                            .filter(round => {
                              if (playerName === "Dan") {
                                return round.creator === "Dad" || round.creator === "Dan";
                              } else if (playerName === 'Debi') {
                                return round.creator === 'Mom' || round.creator === 'Debi';
                              } else {
                                return round.creator === playerName;
                              }
                            })
                            .map(round => {
                                if (selectedRounds[player] != round.title) {
                                    return medianScores[rounds.indexOf(round)];
                                }
                                return 0;
                            })
                            .reduce((acc, score) => acc + (score || 0), 0);

                          const selectedRoundScore = scores[player] && scores[player][selectedRounds[player]] ? scores[player][selectedRounds[player]] : 0;

                          const finalTotal = roundTotal + creatorBonus + selectedRoundScore;

                          return (typeof finalTotal === 'number') ? parseFloat(finalTotal.toFixed(2)) : finalTotal;

                        })()}
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
                  <StyledTableCell key={index}>
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
                            {allPlayers.map((player, index) => (
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
        </TableBody>
      </StyledTable>
    </StyledTableContainer>
    </>
  );
};

export default PlayerTable;
