# `--spec-min-p`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、ルート parser） |
| オプション | `--spec-min-p` |
| 別名 | なし |
| 値 | `P`（数値）。未指定時 `0.0`。正の値で draft 確率の下限を有効化 |

## 役割

MTP draft の確率を見て、次の token を speculative verify window に追加するか決めます。最初の draft は候補に残し、その確率が `P` 以上なら次の draft も窓へ加えます。以降も同じ判定を行い、最初に下限を下回った箇所で窓を止めます。`P=0` 以下ではこの下限判定は無効です。

## 使い方

```sh
# エンジンの token-ID 入力で、draft 確率 0.5 を下限として生成する
strata --pack /path/to/model-pack --tokens "1,2,3" --spec 4 --spec-min-p 0.5

# 常駐 server を起動し、起動時の MTP 下限を 0.5 にする
strata --pack /path/to/model-pack --serve --spec-min-p 0.5
```

`strata` は tokenizer を内蔵しないこの build では `--tokens` または `--tokens-file` を要求します。`--serve` の場合は request が token を持ち込むため省略できます（`engine/src/program/generate.cpp:1208-1215,4996-5005`）。

## 値と既定値

- 通常 parser の内部既定値は `0.0` です。help には setup が `0.5` を書く旨もありますが、これは engine parser の既定値ではありません（`engine/src/program/generate.cpp:1063,1351-1353`）。
- parser は値を `std::atof` で読み取り、ここでは範囲検証や clamp をしていません（`engine/src/program/generate.cpp:4062`）。値を省略すると `next()` が stderr に `<option> needs a value` を出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3847`）。
- 通常の窓幅判定は `P > 0` のときだけ行われるため、0 と負数は実質的に判定を無効にします（`engine/include/strata/spec/window_rule.hpp:61-64`）。
- `--serve` の request 引数 `spec_min_p=...` は別経路で読み取られ、値を `[0,1]` に clamp したうえで、その request が明示したことを記録します（`engine/src/program/generate.cpp:18923`）。これは CLI オプション値の clamp ではありません。

## 実行時の動作

- 通常生成では MTP の draft 概率を `draft_first` / `draft_long` に渡し、確率下限に基づいて窓幅を決めます（`engine/src/program/generate.cpp:24853,24990,25025,25036`; 共通窓規則: `engine/include/strata/spec/window_rule.hpp:57-70`）。`--spec` が窓の上限を決め、`--spec-min-p` はそこまで伸ばす途中の停止条件です。
- server の各 request では初期値に CLI の `o.spec_min_p` を使います。request の `spec_min_p=...` があれば clamp 後の request 値が使われます（`engine/src/program/generate.cpp:18861-18863,18923`）。
- `--draft auto` では、MTP が選ばれた request について、request に `spec_min_p` が明示されていない場合に限り `--draft-mtp-min-p` が `req_spec_min_p` を上書きします。request 明示値が優先されます（`engine/src/program/generate.cpp:1197,19001`）。
- 窓幅規則の優先順位として、MTP の cost-aware 規則が適用されると `--spec-min-p` による窓幅判定は使われません。DFlash2 が有効で `--draft-conf` が正なら、DFlash2 の累積確率積の規則が最後に窓幅を設定します（`engine/include/strata/spec/window_rule.hpp:57-70`）。
- `--batch-mtp` の server 経路でも、MTP chain の各 draft 確率を同じ下限と比較して採用数を決めます（`engine/src/program/generate.cpp:21961-21964,17645-17653`）。

## 適用条件と副作用

- 下限判定は draft が有効で、確率配列がある場合に行われます（`engine/include/strata/spec/window_rule.hpp:61-64`）。draft を使わない実行では窓幅に影響しません。
- 通常の終了統計では `P > 0`、`--draft-conf > 0`、または cost rule のいずれかで窓幅を決めるとき、window size の内訳と `min draft probability` が stdout に表示されます（`engine/src/program/generate.cpp:25264-25268`）。
- `STRATA_SPEC_PROB=1` の gated-proposal 経路では、この値が有限かつ非負でない場合、gated verifier を使わず従来の acceptance rule に戻す旨を stderr に一度警告します。この特殊経路での追加条件であり、一般 parser の値検証ではありません（`engine/src/program/generate.cpp:3547-3561,24845-24853`）。
- このオプション自体によるファイル書き込みや外部プロセス起動は確認できません。生成・server の実行経路において、draft window の幅を制御します。

## 出力とエラー

- オプションに値が続かない場合は stderr にエラーを出して終了コード 2 になります（`engine/src/program/generate.cpp:3844-3847`）。
- 未知の引数は stderr に `unknown argument` を出し、usage を表示して終了コード 2 になります（`engine/src/program/generate.cpp:4267-4274`）。
- 通常 parser には `--spec-min-p` 専用の範囲エラー経路はありません（`engine/src/program/generate.cpp:4062`）。ただし上記 gated-proposal の条件では、不正値に対して警告と fallback があります。

## 根拠

- `engine/src/program/generate.cpp:1063,1351-1353,4062` — 内部既定値、help 表示、CLI parser。
- `engine/src/program/generate.cpp:3844-3847,4996-5005` — 値省略時の失敗と、token 入力の要件。
- `engine/include/strata/spec/window_rule.hpp:16-27,57-70` — MTP と DFlash2 の窓幅規則と相互作用。
- `engine/src/program/generate.cpp:18861-18863,18923,19001` — request ごとの値、clamp、`--draft-mtp-min-p` との優先順位。
- `engine/src/program/generate.cpp:17645-17653,21961-21964,24842-24855,24990-24991,25025-25038,25264-25268` — 実際の生成・batch MTP・統計表示経路。
- `engine/src/program/generate.cpp:3547-3561` — gated-proposal の適用条件と警告 fallback。

調査範囲は上記 commit の `strata` ルート parser とその参照箇所です。異なる専用 parser / executable の同名フラグに関する挙動は、この文書では扱っていません。
