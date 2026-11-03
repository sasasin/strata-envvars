# `FNX_EXPERT_PROFILE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

expert 使用頻度プロファイルのファイルパスを指定します。sFNX の split model loader がこのファイルを読み、GPU に常駐させる routed expert と RAM 側に置く expert の順位付けに使います。環境変数自体は有効・無効を切り替えるフラグではありません。

## 値と判定

値は文字列のまま `std::fopen(path, "rb")` に渡されます。内容の文字列変換や CLI 引数との合成はありません。

| 状態 | 使用するパス・結果 |
|---|---|
| 未設定 | ビルド時の `FNX_DIR` に `/data/expert-routes.bin` を連結したパス |
| 設定あり（空文字を含む） | 設定値をそのままパスとして開く。空文字でも既定パスには戻らず、開けなければエラー |
| 開けるが形式不正 | `2 × NL × NEXP` 個の `unsigned` を読み、さらに EOF であることを要求する。不足・余分なデータ・読み取り失敗はエラー |

拡張子や値の内容による事前検査、範囲 clamp、無効値時の fallback はありません。読み込み後、先頭の `NL × NEXP` 件を decode、次の同数を prompt の tally として使用します。tally を各種の合計で正規化して足し、layer ごとの expert byte 数で割った score の昇順に安定ソートし、冷たい順に RAM 側へ回します。`FNX_EXPERT_RAM_GIB=0` でも cache が有効な限り profile は読み込まれます。

根拠: `src/split/src/model.cpp:1489-1528`。

## 有効になる条件

- CUDA または HIP の sFNX split engine の Flash-Next 構成で使われます。現行 CMake の `strata-split-N` と `split_fnx_run` は `FNX_27B=0` で構築されます。`FNX_27B` が 1 のコード経路では model constructor から `choose_residency()` が呼ばれず、この変数による読み込みもありません。
- `FNX_EXPERT_RAM_GIB` が未設定または `off` 以外であることが必要です。`off` は cache を無効にし、profile 読み込みを省きます。ただし `FNX_ARENA` が既定値または `1` なら、`FNX_EXPERT_RAM_GIB=off` は `FNX_ARENA=0` を要求するエラーになります。
- `FNX_ARENA` は未設定または `1` なら有効、完全一致の `0` なら無効です。それ以外の文字列は profile 読み込み前にエラーです。arena の有無は expert の順位付け score の利用方法を変えますが、cache が有効なら profile 自体は読みます。
- 通常の `Load::PLAIN` は Flash-Next の model load 中に residency を選びます。holder の `Load::HOLD` はこの時点で選ばず、worker の `Load::ATTACH` は復元後に expert を配置する際に選び直します。

根拠: `src/split/src/model.cpp:1433-1443,1475-1493,1550-1565`; `src/split/src/model.hpp:232-265`; `src/split/CMakeLists.txt:92-114,153-160`。

## 実行時の詳細

読み取りは `Model::choose_residency()` の呼び出しごとで、static cache はありません。通常 load では model 初期化時に一度読みます。arena の GPU 配置に空きが足りず expert を追加で RAM に退避する場合、engine は既存 expert を解放して `place_experts()` を再実行し、そのたびに環境変数と profile ファイルを再評価・再読込します。したがって、プロセス開始後の環境変更が再配置時に反映され得ます。通常のサーバーリクエストごとには読みません。

指定または既定のファイルを開けない場合、または期待件数と EOF 条件に合わない場合、`fnx: FNX_EXPERT_PROFILE <path>: not <count> tallies` 例外になります。`sfnx` は `ERR ...` を stdout、`sfnx: failed: ...` を stderr に出して終了コード 1 で終了します。`fnx_run` は stderr に `fnx_run: ...` を出して終了コード 1 です。

根拠: `src/split/src/model.cpp:1489-1499,1550-1552`; `src/split/src/engine.cu:302-315`; `src/split/tools/sfnx.cpp:1030-1035,1055-1061`; `src/split/tools/fnx_run.cpp:1364-1373`。

## 根拠

- 候補名のソース全体検索で、環境から直接値を読む箇所は `src/split/src/model.cpp:1491` のみでした。`src/split/src/model.hpp:252,260` にある記載は説明コメントで、実読み取りは上記 `choose_residency()` です。
- 既定パスの `FNX_DIR` は CMake が split ソースディレクトリを定義して渡しています（`src/split/CMakeLists.txt:64-67,102-114`）。
- `docs/DETAILS.md:85-88` は expert profile を使った配置と `tools/make_profile.py` による作成に触れています。ここでは測定値や profile 作成ツールの別仕様を、この変数の動作としては扱っていません。
