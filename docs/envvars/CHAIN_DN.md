# `CHAIN_DN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`CHAIN_DN` は Apple Silicon 向けの `metal/tests/token_chain.cpp` が、Q2_0 の routed-expert down カーネルに渡すタイル設定を上書きする診断・計測用フックです。通常の `strata` エンジンから読む箇所は見つかりませんでした。`metal/CMakeLists.txt:41-48` は `metal/tests/*.cpp` を個別 executable として追加するため、Metal 用プロジェクトを macOS でビルドした場合の `token_chain` に含まれます（同ファイル `:16-18`）。

候補索引 `docs/envvars/000_envvers.md:63` には名前がありますが、Strata の通常実行経路の設定ではなく、このテスト/計測 executable 内でだけ読み取られます。

## 値と判定

値は `std::sscanf(e, "%d,%d,%d", &dl, &dr, &ds_)` で3つの `int` として読み取られます。必須区切りはカンマです。戻り値を検査しないため、3項すべてが読めなければ未更新の項目は初期値のまま、先行項目だけ読めた場合はその項目だけ更新されます。3項読取後の文字列は検査されません。数値として全体を検証する処理、値域チェック、clamp、無効値の警告や fallback はありません。

| down tensor の型 | 読む環境変数 | 未設定時の `(dl, dr, ds_)` |
|---|---|---|
| Q2_0 | `CHAIN_DN` | `(8, 1, 4)` |
| Q2_0 以外 | `CHAIN_DN4` | `(4, 2, 4)` |

したがって `CHAIN_DN` は down tensor が Q2_0 の場合だけ参照され、他の型では `CHAIN_DN4` が選ばれます。未設定の場合、明示的な空文字を含めて既定タイル値を使います。CLI 引数による上書きはありません。

読み取った値から `gx_dn = N / (ds_ * (32 / dl) * dr)` を計算します（`N` は 2560）。同じ `dl`, `dr`, `ds_` で `moe_down_<型>_<dl>_<dr>_<ds_>` という関数名を組み立て、threadgroup 幅を `32 * ds_` にします。値は kernel 関数選択、dispatch geometry、および `MoeArgs` に渡されます。ゼロなどの不適切な値を防ぐ検査はありません。計算中のゼロ除算等が起こり得る値について、安全な動作は保証されません。

## 有効になる条件

- `token_chain` を実行し、GGUF モデルの routed-expert down tensor に到達すること。
- `CHAIN_DN` が選ばれるのは down tensor の型が Q2_0 の場合だけです。その他の型では同じ場所で `CHAIN_DN4` を読み、`CHAIN_DN` は無視されます。
- `--only` / `--skip` は後段の dispatch 追加を絞りますが、タイル値の読取りと pipeline 名・引数の組立てより後で評価されるため、ここでの環境変数選択自体は抑止しません。
- `metal/CMakeLists.txt:16-18,41-48` によると、この executable は Metal 用 CMake プロジェクトの macOS ビルドに属するテストプログラムです。CUDA/HIP/SYCL の通常実行経路には結び付きません。

## 実行時の詳細

環境変数は `token_chain` が各 routed-expert 層の dispatch を組み立てる際に読みます。`static` cache はなく、該当する層ごとに参照します。選択したタイル値は down カーネル名と `MoeArgs`、threadgroup 幅に反映され、down dispatch に使われます。`--only` / `--skip` のフィルターは `push()` 内で行われ、その直前に down pipeline を要求しているため、フィルターで down dispatch を実行対象から外しても pipeline 作成が試みられます。

この変数専用のログや警告はありません。選択した down 関数が Metal ライブラリにない場合、ランタイムは stderr に `mtl: no function <関数名> ...` を出して終了コード 3 で終了します。pipeline 作成に失敗した場合も `mtl: pipeline <関数名>: ...` を出して終了コード 3 です。これらは環境変数の値検証ではなく、後続の pipeline 生成失敗時の経路です。

## 根拠

- `metal/tests/token_chain.cpp:1-8` — `token_chain` がモデル重みを使う Metal decode-chain の計測ツールである説明。
- `metal/tests/token_chain.cpp:540-546` — 型ごとの初期値、動的な環境変数名、`sscanf` による読取り、`gx_dn` 算出。
- `metal/tests/token_chain.cpp:579-603` — down kernel 名、`MoeArgs`、threadgroup 幅、および down dispatch への値の伝達。
- `metal/tests/token_chain.cpp:162-170,597-603` — `--only` / `--skip` を `push()` で評価する位置。
- `metal/CMakeLists.txt:16-18,41-48` — Metal プロジェクトが macOS 限定で、`tests/*.cpp` から個別 executable を作ること。
- `metal/src/mtl_rt.mm:496-509` — pipeline 関数不在・pipeline 作成失敗時の stderr と終了コード。
