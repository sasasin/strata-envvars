# `--suffix-draft`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、トップレベル引数） |
| オプション | `--suffix-draft` |
| 別名 | なし |
| 値 | 整数 `N`。同じ文脈の過去の出現との最小一致長として使う。 |

## 役割

プロンプトや確定済み出力にある文字列の繰り返しを探し、過去の一致箇所の続きから speculative decoding の候補 token を作ります。候補は検証窓に使われ、モデルの通常出力を置き換える直接出力ではありません。通常の推論経路では、MTP（multi-token prediction）の窓と比べて検証効率がよいとオンライン方針が判断した場合に suffix 候補を使います（`src/program/generate.cpp:773-777,14892-14902`、`src/spec/draft_policy.cpp:123-150`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --suffix-draft 3
```

これはエンジンの usage が示す必須引数 `--pack` と `--tokens` を含む例です。`--tokens` は token ID の例示であり、実際には利用するモデルに対応する prompt token を指定してください（`src/program/generate.cpp:806-812`）。

## 値と既定値

- 省略時は `3` です（`src/program/generate.cpp:773-777`）。
- parser は `atoi` で整数化してから `max(0, 値)` を設定します。負数は `0` になり、`0` は suffix drafting を無効にします。非数値文字列は `atoi` の変換結果に従い、通常は `0` になります。数値の前置部分だけが変換される値も拒否されません（`src/program/generate.cpp:2672`）。
- `N` が正なら drafter を有効にします。実装へ渡す最小一致長は `max(1, N)` ですが、`SuffixDrafter` の constructor がさらに最低 `3` に切り上げます。したがって `1` や `2` はエラーにならず、実効最小一致長は 3 token です（`src/program/generate.cpp:11177,16428`、`src/spec/suffix_drafter.cpp:14-16`）。
- 同じオプションを複数回指定した場合は parser の走査順で後の値が前の値を置き換えます（`src/program/generate.cpp:2416-2420,2672`）。
- 値を省略すると `--suffix-draft needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

有効時、suffix drafter は token 履歴の trigram 索引を保持し、現在末尾の過去の一致候補を最大 64 token まで後方比較して最長一致を選びます。一致長がしきい値に届かなければ候補はありません。履歴は prompt と、検証後に確定した出力 token から構成されます。索引は固定容量の open-addressing table で、生成コードは容量を `max_context + 4096` token として初期化します（`include/strata/spec/suffix_drafter.hpp:7-10,23-31`、`src/spec/suffix_drafter.cpp:14-21,42-67`、`src/program/generate.cpp:11177,14175-14179,14739,15151-15157,16459-16463,16680-16685`）。

MTP を使う通常経路では、`N > 0`、`--spec >= 2`、かつ `--mtp-max-t` が 0 の場合に、元の `--spec` を MTP 窓上限 `--mtp-max-t` に保存し、検証窓の `--spec` を最大 8 まで 2 増やします。`--mtp-max-t` を明示した場合、または `--spec < 2` の場合、この自動拡張は行われません（`src/program/generate.cpp:3205-3210`）。

各窓で suffix 候補の先頭が MTP の先頭予測と一致することを確認します（MTP を使わない場合を除く）。その後 `DraftPolicy::choose` が、観測した候補受理率と窓サイズごとの実測時間・推定時間から token/ms を比較し、MTP より margin 分よいと判断した候補窓を選びます。候補がない、先頭予測が一致しない、または方針が採用しない場合は suffix 窓を選びません。first window では suffix lookup を行いません（`src/program/generate.cpp:14889-14902,16551-16562`、`src/spec/draft_policy.cpp:123-150`）。

`--lookup-chain` と併用した場合、両機能で suffix 履歴索引を共有します。ただし通常の窓では suffix 窓を選んだ round に chained lookup は追加されず、suffix が不採用で、chain の条件を満たすときに別途 chained 候補を検討します（`src/program/generate.cpp:14175-14183,14904-14911,16459-16467,16569-16576`）。

## 適用条件と副作用

- `--suffix-draft 0` は suffix 窓を無効にします。ただし `--lookup-chain` が正なら、chain lookup 用に共通履歴の構築は続きます（`src/program/generate.cpp:14175-14183,16459-16467`）。
- 履歴索引は prompt と確定出力 token をメモリ上に保持します。ソースには索引容量確保の失敗をこの option 固有のエラーに変換する処理は確認できません。ネットワークアクセスやファイル生成はありません（`src/spec/suffix_drafter.cpp:14-21,42-67`）。
- `strata` が Qwen3.6 モデルを識別すると、通常 parser の前に `strata::qwen35::run` へ引数一式を渡します。この専用 parser は `--suffix-draft` を定義していません。通常モードでは未知 option として usage を出して終了コード 2 になり、`--serve` モードでは未対応の長い option として stderr に警告して値を読み飛ばします（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3747,3748-3789`）。
- 索引のリンクは `strata-engine/root/--suffix-draft.md` で、エンジン引数の scope です。`docs/cli/README.md` は Qwen3.6 専用 parser を別 scope として掲示しています（索引 `docs/cli/README.md:1129-1138,1318-1321`）。

## 出力とエラー

通常経路では、suffix 窓の採用数や受理数は `--serve` で stderr に `suffix drafts: ...` として出力されます。通常の generate 経路では `--suffix-draft` が正のとき、終了時の統計に同様の件数を stdout へ出します（`src/program/generate.cpp:15650-15652,16739-16741`）。

不足値は上記のとおり終了コード 2 です。通常 parser で認識されない option は `strata generate: unknown option ...` を stderr に出して終了コード 2 になります（`src/program/generate.cpp:2418-2420,2787-2790`）。Qwen3.6 専用 parser の扱いは「適用条件と副作用」を参照してください。

## 根拠

- parser、既定値、help 表示: `src/program/generate.cpp:773-777,935-936,2416-2420,2672`
- 自動窓拡張、suffix 履歴構築、採用条件: `src/program/generate.cpp:3205-3210,14175-14179,14889-14902,16459-16463,16551-16562`
- 索引と照合の実装: `include/strata/spec/suffix_drafter.hpp:7-10,23-31`、`src/spec/suffix_drafter.cpp:14-21,42-67`
- 採用方針: `include/strata/spec/draft_policy.hpp:29-36`、`src/spec/draft_policy.cpp:123-150`
- serve/generate の統計出力: `src/program/generate.cpp:15650-15652,16739-16741`
- Qwen3.6 の分岐と専用 parser: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3747,3748-3789`
