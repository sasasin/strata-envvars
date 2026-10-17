# `STRATA_SIDE_MIXER`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数の意味は扱わない。

## 役割

検証ウィンドウ（speculative decoding の verifier）が実行する GDN のゲート計算と QSA の indexer 処理を、同じレイヤーの別処理と CUDA stream 上で並行に記録します。モード `1` は GDN ゲートと QSA indexer の枝を有効にし、モード `2` はさらに GDN gate projection と QSA query chain を別の枝にします。環境変数の値は `g_side_mixer()` の関数内 `static` にキャッシュされるため、プロセス内で最初に評価された後の環境変更は反映されません。通常の未設定値は `0` で、分岐は無効です。 (`src/core/verify.cpp:179-181,1006-1016`)

## 値と判定

`getenv()` で得た文字列を `atoi()` で整数変換し、`std::max(0, std::min(2, ...))` で 0〜2 に制限します。文字列全体の妥当性検査はありません。未設定時だけ明示的に `0` となり、空文字や数値に変換できない文字列は `atoi()` により `0` です。数値の後ろに文字が続く場合も `atoi()` が先頭の数値を変換します。

| 入力例 | 判定値 | 動作 |
|---|---:|---|
| unset、空文字、`abc`、`0`、`-1` | 0 | 無効 |
| `1`、`1x` | 1 | GDN ゲートと QSA indexer を分岐 |
| `2`、`2x`、`3`、`99` | 2 | モード1に加え、追加の GDN projection と QSA query を分岐 |

根拠: `src/core/verify.cpp:179-181`。

## 有効になる条件

- この設定が使われるのは `Verifier::record_window()` の検証ウィンドウです。通常の生成処理全体を切り替える設定ではありません。 (`src/core/verify.cpp:986-1009`)
- 初期化時、判定値が 0 より大きいと `side_` / `side2_` の stream と、それぞれの fork/join event を作成します。いずれかの作成に失敗すると初期化は `verify: the mixer branch's stream / events could not be created` で失敗します。 (`src/core/verify.cpp:931-939`)
- `batch_rec_` のウィンドウでは `sidem` と `side_proj` がともに false になり、この設定による GDN/QSA の分岐は実行されません。モードが 1 以上だと `side_mixer` は true のままなので、`STRATA_DF_BRANCH` の分岐条件 `!side_mixer` も満たさなくなります。つまり、このケースでは両方の分岐が使われないことがあります。 (`src/core/verify.cpp:1007-1016,1042`)
- `STRATA_DF_BRANCH` が有効な場合も、`STRATA_SIDE_MIXER` が 1 以上なら `br` が false になり、こちらの mixer 分岐が優先されます。モード 0 ならこの条件による抑止はありません。 (`src/core/verify.cpp:1038-1049`)

## 実行時の詳細

モード 1 では、GDN レイヤーの gate/beta 計算を `side_` に投入し、主 stream 側の projection や convolution と重ねます。GDN recurrence の前に join event を待ちます。QSA レイヤーでは、indexer の key projection、状態 tail の snapshot、key append、query projection、block score と top-k 選択を `side_` に投入し、結果を使う前に主 stream が join を待ちます。 (`src/core/verify.cpp:1309-1315,1371-1385,1502-1548,1590-1597,1607-1620,1668-1675,1755-1763`)

モード 2 では `batch_rec_` でない場合に限り、GDN gate projection と QSA query chain を `side2_` に投入します。各処理は主 stream 上で fork した後、後続処理が結果を読む前に join されます。モード 2 の追加枝が無効なバッチ経路では、モード 1 の枝も `sidem` 条件により無効です。 (`src/core/verify.cpp:1007-1016,1317-1332,1376-1385,1550-1605,1761-1764`)

分岐の fork/join に失敗した場合は `record_window()` が false を返し、対応する `verify: ... branch could not ...` エラー文字列を設定します。デストラクタは作成済み stream と event を破棄します。 (`src/core/verify.cpp:1010-1013,1310-1315,1326-1332,1590-1597,1604-1605,592-595`)

ソースコメントは各枝が同じ入力に対する同じ処理であり、出力を bitwise に保つ意図を記しています。`docs/DETAILS.md` の CUDA opt-in 表もこの設定を「bit-exact」とし、RTX 3060 / RTX A4000（sm_86）の測定表に短いコンテキストでそれぞれ +0.5% / -0.6% と記載しています。この値は同資料の測定条件に限られ、他の GPU やモデル条件へ一般化できません。 (`src/core/verify.cpp:179-180`; `docs/DETAILS.md:2220-2232`)

## 根拠

- 値の読み取り、変換、範囲制限、キャッシュ: `src/core/verify.cpp:179-181`
- stream/event の初期化、失敗時のエラー: `src/core/verify.cpp:931-939`
- verifier 内での各モード、バッチ経路と `STRATA_DF_BRANCH` との関係: `src/core/verify.cpp:1006-1016,1038-1049`
- GDN のモード1/2の枝: `src/core/verify.cpp:1309-1332,1367-1385`
- QSA の mode 1/2 の枝と同期: `src/core/verify.cpp:1488-1500,1550-1605,1668-1675,1755-1764`
- 作成した stream/event の破棄: `src/core/verify.cpp:592-595`
- 資料上の測定条件と記載値: `docs/DETAILS.md:2220-2232`
