# `STRATA_HIPBLASLT_TABLE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

AMD HIP engine の prompt 経路で、engine package に同梱された hipBLASLt tuning table を使うか決める切替です。表が使われると、表にある dense GEMM の shape について hipBLASLt の solution ID を選びます。表がない、または該当 shape / solution が使えない場合は通常の hipBLAS 経路へ戻ります。CUDA / Metal にはこの表の選択処理は適用されません。

アプリの server / setup 側は値を `strata_control.hipblaslt_tuning` で解釈し、選択した表のパスを別変数 `STRATA_HIPBLASLT_TUNING` として engine に渡します。engine を直接起動した場合は C++ 側がこの変数も読み、値が空または未設定なら実行ファイルの隣の `tuning/` から表を探します。そのため、通常の app 経由と engine 直接起動では判定経路が異なります。

## 値と判定

| 読み取り箇所 | 値 | 判定 |
|---|---|---|
| Python app / setup | `off`, `0`, `no`, `false`, `none`, `disable`, `disabled` | 表を使わない。前後空白を除き小文字化して比較する |
| Python app / setup | `on`, `1`, `yes`, `true`, `force`, `enable`, `enabled` | 表を使う。ただしカードと hipBLASLt version に一致する同梱表がある場合 |
| Python app / setup | 未設定、空文字、`auto` | run config の `hipblaslt_table` が真偽値ならそれを優先。それ以外は自動判定 |
| Python app / setup | 上記以外 | 自動判定。無効値としてエラーにはせず、run config の値にも戻らない |
| engine C++ | `off`, `0`, `false` と完全一致 | 同梱表の自動検索をしない |
| engine C++ | それ以外（未設定・空文字を含む） | 同梱表の自動検索を行う |

Python 側は大文字小文字を区別しません（例: `FALSE` は off）。C++ 側の比較は大文字小文字を区別し、Python 側の `no` / `disabled` なども認識しません。C++ 側で `STRATA_HIPBLASLT_TUNING` が空でない場合、`STRATA_HIPBLASLT_TABLE` の off 判定より先にその明示パスが採用されます。

## 有効になる条件

- Python の選択処理は `backend` が `None` または `hip` のときだけ適用されます。server では `exe` が `component:strata-engine` の run config に対して呼ばれます。
- app / setup の自動選択は、同梱表があり、run config の対象 GPU architecture と package の `BUILD.json` にある hipBLASLt version の両方に一致する表がある場合に限り、その表のパスを設定します。表の version やヘッダーが一致しない場合は表を選ばず、説明ログを出します。
- Python 側の現行自動設定は `AUTO_USES_TABLE = False`、`AUTO_ARCHS = ("gfx1151",)` です。従って auto は gfx1151 の一致表だけを選びます。他の architecture は `on` または run config の `hipblaslt_table: true` が必要です。明示的な off は gfx1151 にも優先します。
- ただし app / setup 側が表パスを設定しない場合、engine C++ は独立に動作します。実行ファイルの隣の `tuning/<architecture>-hipblaslt-<version>.txt` が存在し、`STRATA_HIPBLASLT_TABLE` が C++ の off 値と完全一致しなければ、C++ はその表を読み込みます。Python の auto が「使わない」と判定したときにも、この直接起動時の自動検索を抑止する値を app helper は追加していません（`apply()` は path がない場合 config をそのまま返します）。従って、app 側の auto 判定だけから実際に表が無効だとは結論できず、子 engine に継承される `STRATA_HIPBLASLT_TABLE` の値と起動経路を確認する必要があります。
- `STRATA_HIPBLASLT_TUNING` にユーザー指定の非空パスがある場合、通常の選択では Python 側がそれを優先して保ちます。切替が off の場合、Python の `resolve()` は off を先に返しますが `apply()` は path がないと元の config を返すため、既存の `cfg.env` のパス自体は消しません。engine は渡されたパスを現在の GPU architecture と hipBLASLt version に対して検証し、不一致や読み込み失敗なら hipBLASEx に fallback します。

## 実行時の詳細

Python の `mode()` は `os.environ` を run config より先に見ます。認識した on/off 値は config より優先されます。未設定・空文字・`auto` なら config の `hipblaslt_table` が厳密な真偽値 `true` / `false` の場合に反映され、それ以外は auto です。`resolve()` は表を選んだ場合だけ `STRATA_HIPBLASLT_TUNING` のパスを config の `env` に追加します。server は component engine を展開した後、HIP backend の場合にこの処理を呼び、決定メッセージを標準出力に出します。

C++ は `Gemm::init()` / `Gemm::init_external()` ごとに状態作成時に環境を読みます。明示パスがない場合、OS から実行ファイルのパスを取得し、その隣の `tuning/` から、現在の GPU architecture と `hipblasLtGetVersion()` の値を含むファイル名を組み立てます。ファイルがなければ表なしで続けます。状態作成、version / device 照会、表読み込みに失敗した場合は stderr に `using hipBLASEx` を含む診断を出す経路があります。表を読み込むと `prefill gemm: hipBLASLt tuning enabled (...)` を stderr に出します。BF16 / F16 の GEMM 呼び出しは、対応ビルドで表の solution が使えるとき hipBLASLt を試し、それ以外は後続の通常 GEMM 経路を使います。

## 根拠

- Python の値集合、空文字処理、run config の優先順位: `strata_control/hipblaslt_tuning.py:28-41,148-159`。
- package 表の architecture / version / header 照合、自動選択、config 更新: `strata_control/hipblaslt_tuning.py:185-239`。
- server が component engine と HIP backend に対して選択処理を行う箇所: `serve/server.py:8097-8108`。
- 自動選択が gfx1151 に限定される設定: `strata_control/hipblaslt_tuning.py:29-36`。
- app が表パスを設定しない場合に config をそのまま返す処理: `strata_control/hipblaslt_tuning.py:222-239`。
- C++ の直接判定、実行ファイル隣の表検索、読み込みログ: `src/prefill/gemm.cu:252-320`。
- engine 初期化時の状態作成と GEMM 呼び出し: `src/prefill/gemm.cu:651-673,690-713,1018-1025,1135-1141`。
- 資料との照合: `docs/AMD_HIP.md:119-132` と `docs/release-notes-0.2.1.md:42` は、package の表と gfx1151 の自動利用を説明しています。ただし直接起動する C++ の未設定時挙動は、Python 側の `AUTO_ARCHS` 判定と別なので、上記のように区別しました。性能値は調査中に再測定していません。
