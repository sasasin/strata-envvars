# `--kv-grow`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。通常の `generate.cpp` parser） |
| オプション | `--kv-grow` |
| 別名 | なし。反対動作の `--no-kv-grow` がある |
| 値 | 値を取らない真偽フラグ |

## 役割

要求が実際に使う分だけ K/V cache の物理 VRAM を割り当て、長い要求で必要量が増えたときに拡張する。条件を満たすと、拡張分の領域を expert cache から借り、そこにいた expert を cache の別 slot へ移動するか退避する。短い要求の後には K/V の領域を cache へ返す経路もある。これは `--max-context` 自体を縮める指定ではなく、未到達の context 分を開始時に全て物理確保しないための指定である（`engine/src/program/generate.cpp:11441-11447`, `11482-11496`, `11597-11605`）。

## 使い方

```sh
# pack と token 入力を指定して生成時に有効化する
strata --pack pack/full --tokens "1,2,3" --kv-grow
```

フラグ自体は値を取りません。`--no-kv-grow` は parser 上で同じ設定値を false に戻します（`engine/src/program/generate.cpp:3901-3904`）。

## 値と既定値

- `--kv-grow` の既定値は false で、指定すると true になります（`engine/src/program/generate.cpp:824`, `3903`）。
- フラグの後に値は指定しません。余分な値は別引数として解釈され、未知の引数なら usage を表示して終了コード 2 になります（`engine/src/program/generate.cpp:3903-3904`, `4263-4268`）。
- 複数回指定したときは parser が順に代入するため、最後の `--kv-grow` / `--no-kv-grow` が CLI 内の値になります（`engine/src/program/generate.cpp:3903-3904`）。

## 実行時の動作

起動時に `STRATA_KV_GROW` が空でない値で設定されていれば、その先頭文字が `0` かどうかで有効・無効を決め、CLI の値より優先します。空または未設定なら `--kv-grow` / `--no-kv-grow` の結果を使います（`engine/src/program/generate.cpp:7647-7651`）。

要求された場合も、通常 parser では単一 GPU、`--kv-resident` が無効（0 以下）、expert profile 指定あり、CPU 側 expert residency を使わない、expert cache が有効、remote expert cache なし、VMM 利用可能、`--batch` が 0、`--vram-elastic` なし、`--peer-device` なし、という条件をすべて満たすときだけ K/V pool を elastic にします。条件を満たさない場合は標準エラーに無効化理由の要約を出し、通常の固定割り当てで進みます（`engine/src/program/generate.cpp:7651-7661`）。

elastic pool は初期セル数（通常 16,384。`STRATA_KV_GROW_INIT` が正の値ならその値）から始まり、必要量を `STRATA_KV_GROW_STEP`（正の値があれば指定値、既定 8,192 cells）の単位に切り上げ、`--max-context` を上限として拡張します。cache から領域を借りる経路では、expert profile・residency table・expert source・VMM cache range が揃い、cache の slot 上限が floor を超える場合に限り cache slot を使います。揃わなくても elastic pool 自体は有効であれば新規 VRAM から成長し、cache は縮まりません（`engine/src/program/generate.cpp:11448-11474`, `engine/include/strata/core/kv_grow_rules.hpp:23-36`）。

成長前に GPU 処理を静止させ、必要に応じて cache の expert を移動・退避し、K/V 用の VMM chunk を map します。cache が floor に達した後は新規 VRAM を使います。short request の後は、park 中の会話の保持設定がなければ K/V の余剰分を expert cache に返す処理があります（`engine/src/program/generate.cpp:11482-11595`, `19958-19968`）。

## 適用条件と副作用

- `--kv-resident` による K/V streaming、複数 GPU、batch slot、remote expert cache、`--peer-device`、`--vram-elastic` とは併用できません。VMM が使えない環境でも有効化されません（`engine/src/program/generate.cpp:7651-7658`）。SYCL の VMM 実装は `vmm_available()` を常に false とし、この経路を利用不可にします（`engine/sycl/src/core/vmm.cpp:1-13`）。
- K/V が増えると expert cache の保持数が減り、移動対象 expert の device-to-device copy、residency table 更新、VMM map/unmap が発生します。増加先の VRAM を確保できない場合は成長失敗になります（`engine/src/program/generate.cpp:11515-11568`, `11570-11595`）。
- `STRATA_KV_GROW` は CLI の on/off より優先します。特に `STRATA_KV_GROW=0` は CLI で `--kv-grow` を付けても無効にし、空でない `0` 以外の文字列は有効化を要求します（`engine/src/program/generate.cpp:7647-7651`）。
- 索引では Qwen3.6 専用 parser を別の `qwen36/` scope として扱っています。ここで調べた `generate.cpp` root parser の効果をその parser に適用できるかは、本調査では確認していません（`docs/cli/README.md` の Qwen3.6 scope、`docs/cli/000_cli_tools.md:10`）。

## 出力とエラー

要求があるのに適用条件を満たさない場合、`strata generate: --kv-grow is off (...)` を標準エラーへ出し、elastic pool を無効にします（`engine/src/program/generate.cpp:7656-7661`）。実行中の成長で expert 移動、residency table 更新、K/V map が失敗した場合はエラーを標準エラーに出し、呼び出し側が終了コード 1 で終了する経路があります（`engine/src/program/generate.cpp:11553-11568`, `11577-11595`, `23990-23996`）。フラグに値を付けるなど未知引数を渡すと、usage を出して終了コード 2 になります（`engine/src/program/generate.cpp:4263-4268`）。

## 根拠

- parser の既定値とフラグ登録: `engine/src/program/generate.cpp:824`, `3901-3904`。
- help の用途・適用条件: `engine/src/program/generate.cpp:1236-1239`。
- 環境変数優先順位と有効化条件: `engine/src/program/generate.cpp:7644-7661`。
- 初期状態、拡張量、cache slot の移動・失敗: `engine/src/program/generate.cpp:11441-11595`、補助ロジック `engine/include/strata/core/kv_grow_rules.hpp:23-36`。
- SYCL の VMM 非対応: `engine/sycl/src/core/vmm.cpp:1-13`。
- 索引の tool-id と root / Qwen3.6 の parser scope: `docs/cli/000_cli_tools.md:10`、調査リポジトリ側 `docs/cli/README.md:1036-1041`, `1240-1243`。
