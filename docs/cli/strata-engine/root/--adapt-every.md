# `--adapt-every`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数 parser。サブコマンドなし） |
| オプション | `--adapt-every` |
| 別名 | なし |
| 値 | 整数 `N`。通常経路の既定値は `4` |

## 役割

VRAM の expert cache を、推論中に観測した routing 回数に応じて再配置する間隔を指定します。適応の1回では、各層で VRAM 外にあり routing された expert と VRAM 内の expert を比較し、条件を満たすものを入れ替えます。これは主に native pack と GPU expert cache の実行経路の設定で、固定配置にしたい場合は `0` を指定します（`src/program/generate.cpp:688-694`）。

## 使い方

```sh
strata --pack /path/to/pack --tokens '1,2,3' --native /path/to/model.gguf --ple-gguf /path/to/ple.gguf --adapt-every 4
```

`--tokens` は例示した通常の `generate` 経路で必要な入力です。実運用ではモデル・pack に対応する他の必須引数も指定してください。エンジンの usage が示す基本形は `strata generate --pack DIR --tokens ...` です（`src/program/generate.cpp:806-812`）。

## 値と既定値

- 省略時は `4`。明示した値は `std::atoi` で整数へ変換され、同じ引数を複数回渡した場合は parser が順に読み、最後の値が残ります（`src/program/generate.cpp:690-694, 2416-2421, 2626`）。
- `N > 0` は適応処理の間隔として使われます。通常の非 speculative 生成では `N` 回ごとの decode round、serve の単一リクエスト経路では `N` verify window ごと、batch 経路では `N` batch window ごとに判定します（`src/program/generate.cpp:14442-14453, 11588-11600, 10724-10738`）。
- `N <= 0` は適応を無効にします。usage カウンターの確保や適応実行の条件が正値を要求し、Option のコメントにも `0 = static residency` とあります（`src/program/generate.cpp:688-694, 10028-10029, 16185-16186`）。負数も同じ条件で無効になります。
- 数字でない文字列や空文字列は `atoi` の結果 `0` として扱われます。parser にこの値の範囲・書式検証はありません（`src/program/generate.cpp:2626`）。値を省略した場合は `--adapt-every needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

routing が選んだ expert ごとに usage カウンターを加算します。適応時には、各層で VRAM 外の候補のうち decayed usage が `2` 以上のものを上位順に並べ、VRAM 内の最少 usage expert と組にし、usage の差が `--adapt-min-gain`（serve では設定値、通常生成ではコード上 `1.5`）以上の場合に入れ替え候補とします。候補全体は gain 順に並び、実際の上限は `--adapt-swaps` です。従って `--adapt-every` は間隔だけを制御し、1回あたりの交換数は制御しません（`src/core/expert_source.cpp:4822-4826`, `src/program/generate.cpp:10302-10328, 16281-16324`）。

適応後には usage を `--adapt-decay` の値で減衰させます（既定値 `0.7`）。したがって判定は累積 routing 数そのものではなく、過去の利用を減衰させたカウントに基づきます（`src/program/generate.cpp:695, 10446-10460, 16372-16377`）。

`--spec` が2以上で `--adapt-every` を明示していない場合、環境変数 `STRATA_SPEC_ADAPT_EVERY` と `STRATA_SPEC_ADAPT_WARM` が両方有効な値なら、最初の warm-up verify round の間だけ短い間隔を使います。環境変数側の間隔は正値かつ通常間隔より小さく、warm-up round 数も正値である必要があります。明示的な `--adapt-every` はこの調整を抑止します（`src/program/generate.cpp:691-694, 3220-3229`）。

## 適用条件と副作用

- 適応カウンターは `--adapt-swaps` も正値のときに有効です。全 expert が VRAM resident の場合も適応 tier は不要となり、usage 配列を確保しません（`src/program/generate.cpp:10028-10029, 16185-16186`）。
- resident RAM mode では expert を RAM と GPU cache の間で交換するための exchange buffer を予約します。予約に失敗すると stderr に `CPU expert residency: ...` を出し、終了コード `1` で処理を中断します（`src/program/generate.cpp:8250-8263`）。適応中の refill 失敗もエラー経路になります（`src/program/generate.cpp:16322-16326, 16365-16370`）。
- `--serve` では適応交換が GPU cache の配置を変更します。serve の batch 経路では window が完了した後に適応処理を開始し、`--adapt-async` の経路では window 間に進めます（`src/program/generate.cpp:11588-11600, 10724-10752`）。
- AMD iGPU で `STRATA_IO_PREFETCH` が有効かつ適応 tier も有効な場合、メモリー圧迫下で GPU reset が観測された組み合わせとして警告を stderr に表示します。エンジンは値を変更せず実行を続けます（`src/program/generate.cpp:5795-5802`）。
- `--spec` に伴う warm-up 制御を除き、動的な変更や設定ファイルからの優先順位は parser/使用箇所では確認できません。調査したエンジン引数 parser では help usage にこの option の説明が見当たりませんが、parser 自体は受理します（`src/program/generate.cpp:806-812, 2626`）。
- Qwen3.5 MoE の family switch は別実装 `src/qwen35` に引数を渡しますが、その subtree に `--adapt-every` の parser または参照は見つかりませんでした。この文書の動作説明は `src/program/generate.cpp` の共通エンジン経路についてです（`src/program/generate.cpp:2393-2407`）。

## 出力とエラー

適応 tier が稼働した通常生成では、終了時に交換数と間隔を stdout に表示します。serve の resident RAM mode は起動時に adaptive swaps の on/off を stderr に表示します（`src/program/generate.cpp:8264-8270, 16781-16783`）。不明な引数は stderr に `unknown argument` と usage を出して終了コード `2` になります（`src/program/generate.cpp:2787-2792`）。

## 根拠

- parser、数値変換、既定値: `src/program/generate.cpp:688-695, 2416-2421, 2626`
- speculative warm-up 条件: `src/program/generate.cpp:3220-3229`
- usage の加算: `src/core/expert_source.cpp:4822-4826`
- 候補選択、交換上限、減衰: `src/program/generate.cpp:10302-10328, 10446-10460, 16281-16324, 16372-16377`
- 適応周期と実行経路: `src/program/generate.cpp:10724-10752, 11588-11600, 14442-14453`
- RAM 予約と failure: `src/program/generate.cpp:8250-8263`
- AMD iGPU 警告: `src/program/generate.cpp:5795-5802`
- Qwen3.5 への family dispatch: `src/program/generate.cpp:2393-2407`
