# `FNX_PF_HCSPLIT_FULL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

prefill の hyper-connection split（HCSPLIT）経路で、各カードが hyper-connection を読む行範囲を選ぶ。未設定または `0` なら各カードは担当分の行を読む。非ゼロなら各カードが全行を読み、値がちょうど `2` の場合は全行を二つの範囲に分けて 2 回読む。読み取った行の交換処理はこの設定で省略されない。対象実装は `Engine::prefill_pass` とその中の `hc_phase` である（`engine/src/split/src/prefill.cu:1434-1444,1537-1563`）。

この設定は HCSPLIT 自体を有効化しない。HCSPLIT が使われない pass では、値が非ゼロでも通常の読み取り経路に影響しない（`engine/src/split/src/prefill.cu:1436-1444,1621-1650`）。

## 値と判定

`env_int("FNX_PF_HCSPLIT_FULL", 0)` が `std::getenv` で取得し、10 進の符号付き整数として文字列全体を `strtoll` で parse する（`engine/src/split/src/prefill.cu:1438`、`engine/src/split/src/env.hpp:15-21,33-40`）。未設定だけが既定値 `0` になる。先頭・末尾の空白、空文字、数字以外の接尾辞、`long long` の範囲外は整数として受け付けず、例外になる。`+` / `-` は先頭に付けられる。

| 値 | 判定と動作 |
| --- | --- |
| 未設定 | `0`。各カードは担当行範囲を 1 回読む。 |
| `0`（`+0`、`-0` を含む） | `0` と同じ。 |
| `2` | 各カードが全行を二つの範囲に分けて 2 回読む。 |
| その他の非ゼロ整数（例: `1`、`-1`、`3`） | 各カードが全行を 1 回読む。負値も非ゼロとして扱う。 |
| 空文字、`true`、` 1`、`1 `、`1x` | 整数として parse できず、`FNX_PF_HCSPLIT_FULL: '<値>' is not a whole number` の例外になる。 |

数値文字列は末尾まで消費され、全体 parse である。範囲は `long long` として検査されるが、結果は追加の範囲検査なしで `int` に変換される（`engine/src/split/src/prefill.cu:1438`、`engine/src/split/src/env.hpp:15-21,33-40`）。`int` に収まらない整数の変換結果は実装依存となるため、その値の分岐はここでは規定しない。

## 有効になる条件

- 値の parse 自体は `prefill_pass` の最初の呼び出しで行われ、HCSPLIT が無効でも不正値なら例外になる。HCSPLIT の利用条件を満たさない場合、parse された `hs_full` は読み取り範囲の選択に使われない（`engine/src/split/src/prefill.cu:1434-1444`）。
- 実際にこの設定が読み取り行範囲を変えるには、`pf_[0]->hcs` が真であり、pass 内の chunk 数が `FNX_PF_HCSPLIT_MIN` 以上、全 chunk が 512 行以上である必要がある。さらに `FNX_PF_HCSPLIT=1` の場合は各 chunk が 4096 行で、`down_lt` も真でなければ HCSPLIT が解除される。`FNX_PF_HCSPLIT` の既定値は 2（非 HIP 経路）、0 は無効。最小 chunk 数の既定値は 3（`engine/src/split/src/prefill.cu:1090-1102,1436-1444`）。
- HCSPLIT のセットアップは非 HIP ビルドの条件付きコードにあり、2 カード、overlap 有効、`FNX_PF_RING_SM=0`、`FNX_PF_HCSPLIT` 非ゼロが必要。HIP では `p->hcs` を設定するコードがコンパイル対象外であり、この設定は実際の読み取り範囲に作用しない。ただし `hs_full` の parse 自体は `prefill_pass` にあるため、HIP でも不正値は例外になる（`engine/src/split/src/prefill.cu:967-975,1063-1094,1438`）。
- 条件を満たしても HCSPLIT は各 layer の `l > PLE_LAYER` の attention 側の読み取りと、その後の FFN 側の読み取りに使われる。条件が満たされない pass やそれ以前の layer では通常の読み取りが使われる（`engine/src/split/src/prefill.cu:1621-1650`）。
- 他の環境変数や CLI 引数が `FNX_PF_HCSPLIT_FULL` の値を上書きするコードはない。関連する HCSPLIT の有効条件は `FNX_PF_HCSPLIT`、`FNX_PF_HCSPLIT_MIN`、`FNX_PF_OVERLAP`、`FNX_PF_RING_SM` である（`engine/src/split/src/prefill.cu:967-975,1063-1094,1340-1347,1441-1444`）。

## 実行時の詳細

関数ローカル `static const int` として `env_int` の結果を保存するため、プロセス内で最初に `prefill_pass` が呼ばれたときに一度読み、以後の pass では再読しない。プロセス実行中に環境値を変更しても、このキャッシュ値は変わらない。初回の読み取りは HCSPLIT の有効条件判定より前なので、機能が無効なモデル・backend でも値の parse は行われる（`engine/src/split/src/prefill.cu:1434-1444`）。

HCSPLIT がその pass で有効な場合、`hs_full == 0` では各カード `c` が `(c + 1) % NCARD` のカード側に割り当てられた行範囲を読み、非ゼロでは `r0=0, nr=C` として全行を読み取る。`hs_full == 2` だけは `nq=2` となり、`C/2` 行と残りの行に分けて `pf_hc_read_rows` を呼ぶ。値が `2` 以外の非ゼロなら全行を一回で読む。各カードで得た行は `pf_swap_rows` に渡され、後続で join される（`engine/src/split/src/prefill.cu:1541-1563,1587-1593`）。

## ログと測定値

有効値・既定値を通知する専用ログはこの変数の読み取り箇所にはない。値の parse に失敗すると `env_int` が例外を投げ、例外文は `FNX_PF_HCSPLIT_FULL: '<値>' is not a whole number` となる（`engine/src/split/src/env.hpp:33-40`）。sfnx のリクエスト中の prompt read で伝播した場合は stderr に `sfnx: slot %d: the prompt read failed (%s); its lane holds %d tokens, %d pages free`、標準出力のプロトコル行に `ERR prompt read (<cmd> slot <slot>): <理由>` を出す（`engine/src/split/tools/sfnx.cpp:782-790`）。`fnx_run` では stderr に `fnx_run: <理由>` を出して終了コード 1 となる（`engine/src/split/tools/fnx_run.cpp:1364-1373`）。

この変数について、Strata の資料に条件付きの測定値は見つからなかった。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数 parse、unset の既定値、不正値の例外。
- `engine/src/split/src/prefill.cu:967-975,1063-1102` — backend・カード数・overlap・ring・HCSPLIT の初期化条件。
- `engine/src/split/src/prefill.cu:1340-1347,1434-1444` — pass 内の有効条件と設定値の static cache。
- `engine/src/split/src/prefill.cu:1541-1563,1587-1593,1621-1650` — 行範囲の選択、swap、適用される layer。
- `engine/src/split/tools/sfnx.cpp:782-790` — prompt read のエラー出力。
- `engine/src/split/tools/fnx_run.cpp:1364-1373` — `fnx_run` の例外出力と終了コード。
