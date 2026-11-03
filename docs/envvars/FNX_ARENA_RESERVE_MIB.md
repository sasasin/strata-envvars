# `FNX_ARENA_RESERVE_MIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next の sFNX engine が arena を有効にして起動するとき、arena の expert slot と K/V pool の初期ページを配置するために、各 GPU に残しておく VRAM 量を MiB 単位で指定します。既定値は 512 MiB です。この値を予約領域として差し引くことで K/V pool の初期ページ数を抑えます。予約分をこの変数自身が確保する処理はありません。

## 値と判定

共通 helper `env_int` は、未設定なら呼び出し側の既定値を返し、設定値は符号付き十進整数として文字列全体を `strtoll` で読みます。空文字、数字でない文字列、前後の空白、末尾に単位などが付いた文字列、`long long` の範囲外は変換エラーです。先頭の `+` / `-` は受け付けます。変換できても負数は arena 初期化時に拒否されます。

| 環境値 | 結果 |
| --- | --- |
| 未設定 | 512 MiB |
| `0` または `+0` | 予約 0 MiB |
| `1`、`512` などの非負整数 | 指定した MiB 数 |
| `-1` などの負整数 | `FNX_ARENA_RESERVE_MIB: want MiB >= 0, got -1` の例外 |
| 空文字、`abc`、`512 MiB`、前後に空白がある値、`long long` 範囲外 | `FNX_ARENA_RESERVE_MIB: '<値>' is not a whole number` の例外 |

非負の `long long` 値に明示的な上限検査や clamp はありません。値は `size_t` に変換されて `<< 20` されます。したがって、表現可能なバイト数を超える極端に大きな値について、実装は安全な上限値へ制限しません。

## 有効になる条件

- sFNX の Flash-Next engine が `Engine` を構築する経路で参照されます。serve 起動時は `sfnx` がモデルと MTP をロードした後、server を作る前に engine を構築します（`src/split/tools/sfnx.cpp:1050-1059`）。`fnx_run` の各実行モードも共通 engine を構築します（`src/split/tools/fnx_run.cpp:984-988`）。
- Flash-Next の arena 初期化が条件です。27B ビルドではモデルの residency 設定を選ばず、`Model::arena` の初期値 `false` のままなので、この `if (m.arena)` を通りません（`src/split/src/model.cpp:1441-1443`; `src/split/src/model.hpp:255-257`; `src/split/src/engine.cu:283`）。
- `m.arena` が真の場合だけ読み取られます。Flash-Next では `FNX_ARENA` 未設定または値 `1` で arena が有効、値 `0` で無効です。`FNX_ARENA` は文字列全体を比較し、その他の設定値はエラーになります（`src/split/src/model.cpp:1474-1480`）。arena が無効ならこの変数は読み取られず、値が不正でもここではエラーになりません。
- arena を有効にしたまま `FNX_EXPERT_RAM_GIB=off` を指定する組み合わせは、モデル側で先に拒否されます（`src/split/src/model.cpp:1480-1488`）。
- この設定に対応する CLI 引数による上書きは engine の呼び出し箇所にありません。`--max-context` や `--batch` は engine に別引数として渡され、環境値の優先順位を変更しません（`src/split/tools/sfnx.cpp:65-69,82-90,1055-1059`）。

## 実行時の詳細

`Engine` の構築中、arena が有効なら `env_int("FNX_ARENA_RESERVE_MIB", 512)` で値を読み、MiB を bytes に変換します（`src/split/src/engine.cu:283-286`、helper は `src/split/src/env.hpp:15-21,33-40`）。`env_int` に static cache はなく、各 `Engine` 構築時の読み取りです。sFNX server は起動時に engine を一度構築するため、その server の engine については起動時に評価されます。起動後にプロセス環境を変更しても、既に構築された engine の予約値は再評価されません。

arena pool を持つ各カードについて、初期配置後の空き VRAM `fr` と expert slot の大きさ等から必要量 `need` を計算し、その中に `reserve` を加えます。足りない場合は冷たい expert を RAM 側へ移して再配置し、最大 8 回まで調整します（`src/split/src/engine.cu:290-315`）。続く K/V pool のページ数計算でも `fr - slots - reserve` を使うため、予約値が大きいほど初期 K/V ページ数は減ります（`src/split/src/engine.cu:317-329`）。後続で作られる window graph、cuBLAS workspace、lane page table 用に空きを見込む意図は同ファイルのコメントに記されています（`src/split/src/engine.cu:276-282`）。

負値や整数変換エラーは例外になります。arena の K/V pool と lane block が収まらない場合は、空き量・slot 量・予約量を含む `FNX_ARENA: card ... has ... MiB free ...` 例外になります（`src/split/src/engine.cu:323-329`）。sFNX serve は例外内容を stdout の `ERR ...` と stderr の `sfnx: failed: ...` に出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1027-1035,1055-1061`）。`fnx_run` は stderr に `fnx_run: ...` を出して終了コード 1 を返します（`src/split/tools/fnx_run.cpp:1364-1373`）。正常起動時に、この予約値自体を表示するログは確認できません。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:519-523`（候補掲載は実装根拠として扱わず、実コードで確認）。
- 値の parse と既定値: `src/split/src/env.hpp:15-21,33-40`。
- arena 有効条件と関連設定: `src/split/src/model.cpp:1472-1488`。
- 予約値の読み取り、MiB 変換、arena sizing、再配置、ページ数計算、失敗経路: `src/split/src/engine.cu:276-329`。
- serve での engine 構築と例外表示・終了: `src/split/tools/sfnx.cpp:1027-1035,1050-1061`。
- `fnx_run` の engine 構築と例外表示・終了: `src/split/tools/fnx_run.cpp:984-988,1364-1373`。
