# `--mtp-q4`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ `strata` 推論エンジン（`generate` 引数 parser） |
| オプション | `--mtp-q4` |
| 別名 | なし |
| 値 | `all`、`proj`、`head` のいずれか |

## 役割

MTP（multi-token prediction）ドラフターの一部重みを、ロード時に Q4_0 形式へ変換し、ドラフト生成の重み読み出しを小さくするための opt-in 設定です。`proj` はドラフト層の投影重み、`head` はドラフト head、`all` は両方を対象にします。検証側の出力が変わる設定ではなく、MTP が提案した token は引き続き verify window で判定されます（`src/core/mtp.cpp:190-222`, `src/core/mtp.cpp:225-248`, `src/program/generate.cpp:5461-5472`）。

## 使い方

モデル pack と MTP runtime を指定する通常のエンジン呼び出しに追加します。

```sh
strata --pack pack/full --tokens "1,2,3" --native --mtp path/to/mtp-runtime --spec 4 --mtp-q4 all
```

`--mtp` と `--spec` はこの例で MTP ドラフターをロードするための関連引数です。`--mtp-q4` 自体は値を一つ取ります（`src/program/generate.cpp:741-745`, `src/program/generate.cpp:2684-2690`）。

## 値と既定値

- `all`: Q8_0 投影重みとドラフト head の対象行を Q4_0 化します。
- `proj`: Q8_0 投影重みだけを Q4_0 化します。
- `head`: ドラフト head の対象行だけを Q4_0 化します。
- 省略時は無効です。Options の `mtp_q4` は空文字列で初期化されます（`src/program/generate.cpp:788-789`）。
- 値は大文字小文字を区別して上記3つだけを受理します。無効値は stderr に `strata generate: --mtp-q4 takes all, proj or head` を出し、終了コード 2 で終了します。値を省略した場合も parser の共通処理が `--mtp-q4 needs a value` を stderr に出して終了コード 2 にします（`src/program/generate.cpp:2416-2420`, `src/program/generate.cpp:2684-2689`）。
- 同じオプションを複数回指定した場合、重複拒否処理はなく後の値が上書きします（`src/program/generate.cpp:2416-2420`, `src/program/generate.cpp:2684-2689`）。

## 実行時の動作

parser は文字列を `Options::mtp_q4` に保存し、MTP オブジェクトへ渡すとき `all` / `proj` / `head` を投影重み用と head 用の二つのフラグに分けます。設定はロード前に適用されます（`src/program/generate.cpp:788-789`, `src/program/generate.cpp:5460-5463`, `include/strata/core/mtp.hpp:64-67`）。

`proj` が有効なら、MTP runtime の `dense.bin` から Q8_0 で列数が32の倍数の tensor を選び、Q8_0 から float に展開して ggml の Q4_0 quantizer で再量子化し、別の device buffer に置きます。実行中の各投影はその Q4_0 コピーがある場合に選び、なければ元の Q8_0 を使います（選択関数と変換: `src/core/mtp.cpp:178-188`, `src/core/mtp.cpp:190-222`, load 時の呼出し: `src/core/mtp.cpp:295-308`; 投影での使用: `src/core/mtp.cpp:884-906`, `src/core/mtp.cpp:1007-1014`）。従って元の dense 重み buffer に加えて Q4_0 コピー分の device memory も必要です。

`head` が有効で通常の draft vocabulary subset が使われる場合、main native head から subset 行を取り出し、読み出せる元形式かつ embedding 幅が32の倍数なら行を Q4_0 化して draft head buffer に書き戻します。ドラフト head が使う token 行数は `draft_vocab.bin` による subset の行数です（`src/core/mtp.cpp:692-740`, `src/core/mtp.cpp:225-248`）。`STRATA_MTP_FULL_HEAD=1` の診断経路では subset 行の作成ブロック自体を通らないため、この `head` 変換も行われません（`src/core/mtp.cpp:507-513`, `src/core/mtp.cpp:692-694`）。

MTP runtime が指定されていない場合、または `--spec` が2未満で MTP runtime が無効化された場合、`--mtp-q4` の値は parser で受理されますが、MTP の load が呼ばれないため変換は行われません（`src/program/generate.cpp:5455-5472`）。`--draft dflash2` など別の drafter 選択もありますが、このフラグの設定先は MTP drafter です。

Metal backend の `MtpDrafter::load` は `metal_engine::mtp_load` に早期委譲します。この経路では CUDA / SYCL 実装の `q4_` / `q4_head_` 変換処理を実行しないため、Metal でこの引数が受理されても Q4_0 化は確認できません（`src/core/mtp.cpp:251-258`）。CUDA と SYCL の実装では同じ値分解と変換処理があります（`sycl/src/program/generate.cpp:1971-1977`, `sycl/src/program/generate.cpp:4180-4197`, `sycl/src/core/mtp.cpp:194-227`, `sycl/src/core/mtp.cpp:230-255`）。

## 適用条件と副作用

- `--mtp` が実際にロードされる実行で効果があります。ロード条件として `--spec` は2以上である必要があります。`--native` の main head がドラフト head bind に必要です（`src/program/generate.cpp:5455-5472`, `src/core/mtp.cpp:661-675`）。
- `STRATA_NATIVE_EXPERTS` なしでビルドされた CUDA / SYCL 実装では、Q4_0 化関数は `mtp: --mtp-q4 needs a build with native experts (ggml)` をエラーとして返します（`src/core/mtp.cpp:218-221`, `sycl/src/core/mtp.cpp:223-226`, `sycl/src/core/mtp.cpp:252-255`）。
- 投影側の Q4_0 コピーが VRAM に確保できない場合は `mtp: the Q4_0 projections do not fit`、head の型を読み取れないか幅が32の倍数でない場合は `mtp: --mtp-q4 cannot read the head's format`、head の device 間コピー失敗時は読み出し・書き込みエラーになります（`src/core/mtp.cpp:190-248`）。これらは MTP load 失敗となり、CLI はエラーと VRAM free 情報を stderr に出して終了コード 1 を返します（`src/program/generate.cpp:5472`）。
- 変換時には MTP 重みの読み書きと device memory の確保が発生します。head 変換では head subset を一度 host memory へコピーして変換後に device へ戻します（`src/core/mtp.cpp:225-244`）。ロード成功時の変換状況は stderr の `strata mtp: --mtp-q4: ...` 行で報告されます（`src/core/mtp.cpp:216-216`, `src/core/mtp.cpp:242-243`）。
- Q4_0 再量子化による出力品質・速度の変化量はソースだけでは定量化できないため、ここでは性能や品質を断定しません。

## 調査範囲

索引の `strata-engine/root` scope に従い、トップレベル engine の parser と MTP load / bind を確認しました。CUDA `src/` と SYCL `sycl/` の実装は確認しましたが、Metal は委譲先の `metal/src/engine/window.cpp` における MTP load 内部を調査していません。Release 配布物や実機での動作確認は行っていません。

## 根拠

- parser、usage、既定値、値 validation: `src/program/generate.cpp:741-745`, `src/program/generate.cpp:788-789`, `src/program/generate.cpp:2416-2420`, `src/program/generate.cpp:2684-2690`
- MTP load への設定・失敗処理: `src/program/generate.cpp:5455-5472`
- 投影重みの変換と選択: `src/core/mtp.cpp:178-222`, `src/core/mtp.cpp:308-308`
- draft head subset の bind、変換、full-head 条件: `src/core/mtp.cpp:507-513`, `src/core/mtp.cpp:661-740`
- MTP interface と draft head の挙動: `include/strata/core/mtp.hpp:64-67`
- SYCL 実装の parser、設定、Q4_0 変換: `sycl/src/program/generate.cpp:1971-1977`, `sycl/src/program/generate.cpp:4180-4197`, `sycl/src/core/mtp.cpp:194-227`, `sycl/src/core/mtp.cpp:230-255`
- 索引の tool/scope: `docs/cli/README.md:1128-1135`, `docs/cli/README.md:1203-1208`
