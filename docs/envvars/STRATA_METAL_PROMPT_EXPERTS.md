# `STRATA_METAL_PROMPT_EXPERTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal のストリーミング prompt GEMM が使う routed expert の gate/up と down の kernel family を `v2` または `v3` に決める。対象は `Window::prompt_gemm_init` が作る `PromptGemm` で、実行時には `mm_gu3_...` / `mm_down3_...` または `mm_gu2_...` / `mm_down2_...` の pipeline 名と function constant に反映される。`v3` は `p.k4`（cooperative layout の実行時判定結果）も function constant として渡す。`engine/metal/src/engine/window.cpp:3061-3064, 3328-3334, 3367-3388`。

## 値と判定

コードは `std::getenv` で設定有無を調べ、設定されていれば `std::string(eg) == "v3"` と完全一致比較する。大文字小文字を区別し、trim や数値変換はしない。従って未設定だけが `p.k4` に応じた既定値になり、空文字や `v2`、`V3`、`v3 `、その他の文字列はすべて `v2` 側（`false`）になる。無効値の警告や別値への fallback はない。モデルの gate expert 型が条件に該当すると、設定値にかかわらず `v2` に固定される。`engine/metal/src/engine/window.cpp:3061-3066`。

| 条件 | 未設定 | 設定時に v3 になる値 | 設定時に v2 になる値 |
|---|---|---|---|
| streamed `PromptGemm`、gate expert 型 `< 144` | `p.k4 == true` なら v3、false なら v2 | `v3` | 空文字、`v2`、`V3`、`v3 `、`1`、`0` など（`v3` との完全一致以外） |
| streamed `PromptGemm`、layer 0 の `blk.0.ffn_gate_exps.weight` の型 `>= 144` | v2 | v3 を指定しても v2 | すべて v2 |

`p.k4` は `coop_k4` の結果であり、`COOP_K4` が設定されていれば `atoi` が 0 以外かで判定し、未設定なら GPU 上の cooperative layout probe の結果を使う（`engine/metal/src/engine/prompt_chain.inc:26-47`）。この環境変数そのものに `v2` という特別な設定値はなく、未設定時の既定値とも異なり得る。

## 有効になる条件

- Apple 向け Metal engine が必要。`engine/metal/CMakeLists.txt:1-2, 18-20, 103-108`。
- `prompt_run_rows` がストリーミング経路に入り、`STRATA_METAL_PROMPT=window` ではなく、かつ `STRATA_METAL_PROMPT_GEMM` が文字列 `0` でないことが必要。この経路では `STRATA_METAL_PROMPT_GEMM_MIN`（未設定時 64）以上の prompt 長で `prompt_gemm_init` と `prompt_chunk` が使われる。`engine/metal/src/engine/window.cpp:3743-3766`。
- `STRATA_METAL_PROMPT_GEMM=0` の場合はストリーミング GEMM 初期化が省かれ、prompt は decode window の `run` / `commit` 経路になる（`engine/metal/src/engine/window.cpp:1793-1808, 3767-3775`）。`STRATA_METAL_PROMPT=window` の場合も prompt GEMM 経路を選ばない（同 `3746-3766`）。
- 常駐モデルの prompt は `Window::prompt` / `pc_setup` の prompt chain を使い、この変数を読まない。こちらの expert variant は `COOP_K4` と gate expert 型から決まるため、本変数を設定しても適用されない（`engine/metal/src/engine/prompt_chain.inc:26-47, 65-75, 583-597`; 呼び出し側 `engine/metal/src/engine/window.cpp:3748`）。
- `PromptGemm` では layer 0 の gate expert tensor 型が `>= 144` なら v3 kernel family は無効になる。コードはこの型だけを条件に使い、各層を個別に調べていない（`engine/metal/src/engine/window.cpp:3062-3064`）。
- CLI 引数による上書きや優先順位はこの読み取り箇所にはない。プロセスの環境から直接読み取る。

## 実行時の詳細

ストリーミング arena の初期化後、prompt GEMM が有効なら `prompt_gemm_init` が `PromptGemm` を一度作成する。そこで `STRATA_METAL_PROMPT_EXPERTS` を読み、設定した kernel family を `p.gu_v3` / `p.dn_v3` に保持する。すでに `pg_` があると初期化関数は直ちに成功して再読込しないため、同じ `Window` の稼働中に環境を変更しても反映されない。初期化時に作られた設定は、各 chunk の expert pipeline 選択に使われる（`engine/metal/src/engine/window.cpp:3037-3040, 3061-3066, 3123-3126, 3328-3334, 3367-3388`）。

`v3` の明示指定は cooperative layout probe の `p.k4` が false でも v3 family を選択する。Strata 側にこの指定を `v2` に戻す追加判定は見当たらない。kernel pipeline の作成・実行時に非対応環境でどう失敗するかは、この環境変数を読むコードからは特定できないため、ここでは外部 Metal runtime の挙動を断定しない。

## ログと測定値

初期化が成功すると stderr に `strata metal: prompts on the matrix units in chunks of ... (experts v3|v2, QSA ..., matmul2d layout K4|other; ... GB of buffers...)` を出し、選ばれた family を確認できる（`engine/metal/src/engine/window.cpp:3123-3126`）。layer 0 の gate expert 型が `>= 144` で v3 指定が抑止されても、このログは最終的な `v2` を示す。環境変数自体の無効値に対する警告・エラー出力はない。

この変数の効果を条件付きで測定した Strata 資料は、調査範囲では確認できなかった。

## 根拠

- `engine/metal/src/engine/window.cpp:3061-3066` — cooperative layout と変数値を使った選択、trellis 型による v3 抑止。
- `engine/metal/src/engine/window.cpp:3328-3334, 3367-3388` — v2/v3 ごとの tile、pipeline 名、function constant と dispatch。
- `engine/metal/src/engine/window.cpp:1793-1808, 3743-3775` — GEMM 初期化と prompt 経路の選択条件。
- `engine/metal/src/engine/prompt_chain.inc:26-47, 65-75, 583-597` — resident prompt chain の別個の判定と実行。
- `engine/metal/CMakeLists.txt:1-2, 18-20, 103-108` — Metal build の Apple 限定。

## 資料との食い違い

Strata の `docs/MAC.md:273` はこの変数を `v3` 指定時の M5 layout とし、既定を v2 と記載する。一方、現行 `PromptGemm` 実装は未設定時に `p.k4` を既定値とする。`docs/SETTINGS.md:173` も値の型を「on / off」としているが、実装は `v3` との完全一致だけを v3 指定として認識する。また、索引 `docs/envvars/000_envvers.md:1461` は候補として名前を掲載している。文書は現行ソースの挙動を記述した。
