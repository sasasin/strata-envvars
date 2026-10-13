# `STRATA_SPEC_COUPLED`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの動作は対象外。

## 役割

MTP（multi-token prediction）draft 層が、通常の argmax ではなく、要求の sampler 設定と乱数を使って draft token をサンプルする機能を有効にします。draft の採用判定は引き続き verifier が行います。対象は `--mtp` で MTP drafter を使う実行経路です。CUDA/HIP 共通の実装と SYCL 実装に同じ環境変数判定があります。

## 値と判定

`getenv()` で値を取得し、未設定、空文字列、または文字列全体がちょうど `"0"` のとき無効です。それ以外の非空文字列は有効です。数値変換や真偽値の文字列解釈はありません。

| 環境変数値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字列 | 無効 |
| `0` | 無効 |
| `1`、`00`、`false`、` 0`、`0 ` など | 有効 |

判定結果は helper の関数内 `static bool` に初回呼び出し時に保存されます。通常は起動時のオプション初期化で読み取られ、その後は `--coupled-draft` / `--no-coupled-draft` の処理が同じ状態を上書きします。プロセス起動後に環境を書き換えても再読込されません。

根拠: `include/strata/core/coupled_draft.hpp:57-63`, `sycl/include/strata/core/coupled_draft.hpp:55-61`; オプション初期値と CLI 上書きは `src/program/generate.cpp:437,1962-1963,2233`, `sycl/src/program/generate.cpp:507,1797-1798,2007`。

## 有効になる条件

- MTP drafter が選択されている必要があります。generate 経路では `o.mtp` が空でないとき `mtp.bind()` を呼び、server 経路も MTP を使う要求で drafter の sampler 設定を渡します。
- 値が有効でも、greedy 要求や温度 0 では coupled sampling は実行されず、draft 層は通常経路を使います。CUDA/HIP ではさらに `STRATA_SPEC_MIN_TEMP` の閾値未満の温度も対象外です。SYCL 実装にはこの閾値判定がありません。
- `--no-coupled-draft` は環境変数由来の有効状態を無効化できます。両方の CLI オプションを指定した場合は、引数列で後に処理された方が状態を決めます。
- `src` 側（CUDA/HIP）は `STRATA_SPEC_PROB` が有効な場合にも coupled 用バッファを準備します。`STRATA_SPEC_PROB` 自体の判定・挙動とは別に、CUDA/HIP の `coupled_draft_env()` がこの環境変数を OR 条件に含めています。SYCL 側の helper は `STRATA_SPEC_COUPLED` だけを見ます。
- draft logits の語彙幅に対して sampler scratch を確保できない場合、coupled setup は警告を出して成功扱いで戻り、argmax draft に fallback します。必要バッファの確保自体に失敗した場合は bind が失敗します。

根拠: MTP 使用と sampler 設定は `src/program/generate.cpp:12952-12959,11095-11098`; 実行時の sampler 条件は `src/core/mtp.cpp:576-581`, `sycl/src/core/mtp.cpp:667-672`; CUDA/HIP の helper 合成は `include/strata/core/coupled_draft.hpp:65-79`; bind/setup と幅 fallback は `src/core/mtp.cpp:520-522,525-543,565-573,682`, `sycl/src/core/mtp.cpp:603-605,608-625,658-660,782`。

## 実行時の詳細

MTP bind 時、環境変数または CLI 状態により coupled 用 sampler parameter、penalty history ring、scratch などを準備します。CUDA/HIP では setup 成功時に stderr へ `strata mtp: coupled draft sampling on (STRATA_SPEC_COUPLED): sampled requests draft with the target's chain and Philox draw over ... tokens` を出します。SYCL も同じ趣旨のログを出します。server は要求ごとに sampler parameter を渡し、generate は CLI の sampler parameter を渡します。greedy でない場合、draft 層が target 側と同じ sampler chain と Philox draw を用いる経路に入り、verify window が draft を照合します。

CUDA/HIP では `STRATA_SPEC_PROB` も有効なら setup ログと draft sampling 経路は probabilistic acceptance 用になります。coupled setup が語彙幅を扱えない場合の警告文字列は `strata mtp: STRATA_SPEC_COUPLED: %lld draft logits are too wide for the coupled sampler; argmax drafts` です。

根拠: `src/core/mtp.cpp:525-573,576-581,999-1009,1068-1076`; `sycl/src/core/mtp.cpp:608-660,667-672,1129-1134,1228-1238`; request/CLI からの設定は `src/program/generate.cpp:11095-11098,12952-12959`。

## 文書との照合

`docs/DETAILS.md:114-126` は、サンプリング要求で opt-in の coupled drafts として説明しています。また RTX 3060、IQ3_XXS、`--spec 4 --mtp`、温度 1.0 / top_p 0.95 / top_k 20 の記載条件で、採用 draft の割合が 62.1% から 66.9% になった一方、速度差は run-to-run spread を超えなかったと記しています。これは資料記載の測定結果であり、ここで再測定したものではありません。実装では greedy 要求は sampler 条件により対象外です。

## 根拠

- 環境変数の parse/cache、CLI で変更する共有状態: `include/strata/core/coupled_draft.hpp:57-83`; `sycl/include/strata/core/coupled_draft.hpp:55-69`
- CUDA/HIP setup、幅 fallback、ログ、要求 sampler 条件: `src/core/mtp.cpp:518-573,576-581,682`
- SYCL setup、ログ、要求 sampler 条件: `sycl/src/core/mtp.cpp:601-660,667-672,782`
- CLI と server/generate 呼び出し元: `src/program/generate.cpp:437,906-907,1962-1963,2233,11095-11098,12952-12959`
- 設計説明・測定条件: `docs/DETAILS.md:114-126`
