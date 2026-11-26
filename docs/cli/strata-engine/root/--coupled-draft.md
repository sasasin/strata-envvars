# `strata --coupled-draft`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。サブコマンドなし） |
| オプション | `--coupled-draft` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

MTP drafter が通常の argmax draft を作る代わりに、sampling が有効な要求で target 側と連動した分布 sampling を使うようにします。MTP が設定されていない場合、このフラグだけでは drafter は使われません。対象 parser は通常の `engine/src/program/generate.cpp` と SYCL 用 `engine/sycl/src/program/generate.cpp` にあります。

## 使い方

```sh
# MTP を使う推論で、coupled draft sampling を有効にする
strata --pack /path/to/pack --tokens "1,2,3" --mtp /path/to/mtp --coupled-draft
```

pack と MTP のパス、token ID は実際のモデルに合わせて指定してください。オプション自体に値は続けません。

## 値と既定値

- 値を取りません。parser は `--coupled-draft` を見つけると設定を `true` にし、形式・数値範囲などの追加 validation はありません（`engine/src/program/generate.cpp:3978`、`engine/sycl/src/program/generate.cpp:1996`）。
- 初期値は `STRATA_SPEC_COUPLED` の読み取り結果です。変数が未設定・空・文字列 `0` なら `false`、それ以外の非空文字列なら `true` です（`engine/src/program/generate.cpp:873`、`engine/include/strata/core/coupled_draft.hpp:57-62`）。
- `--coupled-draft` と `--no-coupled-draft` は引数の出現順に同じ設定値を書き換えるため、最後に指定した方が設定値になります（`engine/src/program/generate.cpp:3978-3979`、SYCL parser: `engine/sycl/src/program/generate.cpp:1996-1997`）。
- CUDA/HIP 実装では、`STRATA_SPEC_PROB` が非空かつ `0` 以外の場合、coupled 用のセットアップ自体も環境変数側から有効になります。これは本フラグの真偽設定とは別の条件です（`engine/include/strata/core/coupled_draft.hpp:65-79`）。SYCL 側の `coupled_draft_env()` は `STRATA_SPEC_COUPLED` 状態だけを返します（`engine/sycl/include/strata/core/coupled_draft.hpp:54-70`）。

## 実行時の動作

parser 完了後、`Options::coupled_draft` は `set_coupled_draft()` に渡され、環境変数から初期化した状態を CLI の設定で更新します（`engine/src/program/generate.cpp:4614`、`engine/include/strata/core/coupled_draft.hpp:81-83`）。MTP drafter の bind 時に coupled 用バッファを初期化し、設定が有効なら draft logits 用 scratch、sampling parameter、履歴 ring などを確保します（`engine/src/core/mtp.cpp:802-825,1014-1015`）。

CUDA/HIP では要求ごとに、MTP が利用可能で、sampling が greedy ではなく、temperature が 0 より大きく、かつ `spec_min_temp()` 以上の場合に限って coupled sampling が active になります。`STRATA_SPEC_MIN_TEMP` の既定値は `0.0` で、値が指定されれば要求温度の下限として使われます（`engine/include/strata/core/spec_prob.hpp:64-73`）。SYCL では greedy でなく temperature が 0 より大きいことが条件で、`STRATA_SPEC_MIN_TEMP` の閾値判定はありません（`engine/sycl/src/core/mtp.cpp:737-742`）。条件を満たさない要求では通常の argmax draft 経路を使います（CUDA/HIP: `engine/src/core/mtp.cpp:855-860,1521-1539`）。有効時は target の chain と Philox draw を使う coupled sampler に draft logits を渡します（同 `mtp.cpp:1521-1531`）。生成側は sampling parameters を verifier と MTP drafter に設定します（`engine/src/program/generate.cpp:24538-24542`）。

## 適用条件と副作用

- MTP を有効にした経路に適用されます。生成側は `--mtp` 設定から `use_mtp` を決め、MTP が有効なときだけ `mtp.bind()` を呼びます（`engine/src/program/generate.cpp:24507-24510`）。
- coupled 機能のセットアップで GPU 側バッファ、sampling parameter、履歴 ring、必要に応じ draft head の token map を確保します。サイズは語彙数と MTP window に依存します（`engine/src/core/mtp.cpp:802-837`）。SYCL 実装も対応する device allocation と mapping を行います（`engine/sycl/src/core/mtp.cpp:678-711`）。
- scratch サイズ関数が `0` を返すほど draft logits が広い場合は stderr に `too wide ...; argmax drafts` と出力してセットアップを成功扱いにし、coupled sampling を使わず argmax drafts に戻ります（CUDA/HIP: `engine/src/core/mtp.cpp:802-809`、SYCL: `engine/sycl/src/core/mtp.cpp:678-685`）。
- 設定の有効化だけでは sampling が greedy / temperature 0 の要求に作用しません。CUDA/HIP ではさらに `STRATA_SPEC_MIN_TEMP` 未満の要求も対象外です（`engine/src/core/mtp.cpp:855-857`、`engine/include/strata/core/spec_prob.hpp:64-73`）。CUDA/HIP では `STRATA_SPEC_PROB` が coupled の同じセットアップ資源を有効化する別機能です（`engine/include/strata/core/coupled_draft.hpp:65-79`）。SYCL 版の環境変数判定にはこの条件はありません（`engine/sycl/include/strata/core/coupled_draft.hpp:54-70`）。

## 出力とエラー

coupled のセットアップ成功時は stderr に `coupled draft sampling on` の起動メッセージが出ます（CUDA/HIP: `engine/src/core/mtp.cpp:842-852`、SYCL: `engine/sycl/src/core/mtp.cpp:728-731`）。scratch 不適合時の fallback メッセージも stderr に出ます（上記参照）。バッファ、mapping、token map の確保に失敗すると `setup_coupled()` がエラー文字列を返し、MTP bind が失敗します（CUDA/HIP: `engine/src/core/mtp.cpp:811-820,831-840,1014`、SYCL: `engine/sycl/src/core/mtp.cpp:691-695,705-726,875`）。生成側は bind エラーを stderr に出して終了コード `1` を返します（`engine/src/program/generate.cpp:24508-24510`）。

未知の引数は `unknown argument` と usage を stderr に出し、parser が `2` を返します。`--coupled-draft` は引数を取らないため、直後の別 option を値として消費しません（`engine/src/program/generate.cpp:4268-4273`、SYCL: `engine/sycl/src/program/generate.cpp:2214-2219`）。

## 根拠

- `engine/src/program/generate.cpp:873,1478-1479,3978-3979,4614` — 既定設定、help 表示、parser、CLI 設定の反映。
- `engine/include/strata/core/coupled_draft.hpp:57-83` — CUDA/HIP 側の環境変数解釈、`STRATA_SPEC_PROB` との関係、状態更新。`engine/sycl/include/strata/core/coupled_draft.hpp:54-70` — SYCL 側の判定。
- `engine/include/strata/core/spec_prob.hpp:64-73` — `STRATA_SPEC_MIN_TEMP` と sampling 温度下限。
- `engine/src/core/mtp.cpp:802-852,855-860,1014-1015,1521-1539` — セットアップ、sampling の適用条件、実際の sampler 呼び出しと fallback。
- `engine/src/program/generate.cpp:24507-24510,24538-24542` — MTP bind と生成時の sampling 設定。
- `engine/sycl/src/program/generate.cpp:551,1015-1016,1996-1997,2231`、`engine/sycl/src/core/mtp.cpp:678-742,875` — SYCL 側 parser・状態反映・セットアップと sampling 条件。
