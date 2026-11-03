# `strata` `--ram-keep-gib`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root） |
| オプション | `--ram-keep-gib` |
| 別名 | なし |
| 値 | `W`: GiB 単位の数値。0 以上。内部値は byte に変換され、最大 1024 GiB に制限される |

## 役割

expert の常駐方式を選ぶ起動時の RAM 目安を指定します。指定量 `W` GiB をユーザー作業用に空けられる場合に expert arena を使い、arena が使えないときの RAM copy fallback では少なくとも `W` GiB（または platform の安全 headroom）を残すようにします。ヘルプでは既定値 0 と説明されています（`src/program/generate.cpp:1285-1289`）。

## 使い方

```sh
strata --pack /path/to/model --ram-keep-gib 12 --tokens '1,2,3'
```

この例は通常の `strata generate` 経路に 12 GiB を残す指定です。実行ファイルが受け付ける値は `--ram-keep-gib` の直後の引数で、parser はこれを `std::atof` で読みます（`src/program/generate.cpp:3293-3298,3657-3661`）。

## 値と既定値

- 省略時は 0 byte です（`Options::ram_keep` の初期値、`src/program/generate.cpp:721-725`）。
- CLI 値は `std::atof` で `double` に変換され、`gib >= 0` を満たさない場合は stderr に `strata generate: --ram-keep-gib needs N >= 0` を出して終了コード 2 になります。引数自体が欠けている場合は `needs a value` を stderr に出して終了コード 2 です（`src/program/generate.cpp:3295-3297,3657-3661`）。
- GiB から byte への変換は `ram_keep_from_gib` が行い、0 以下は 0、1024 GiB 以上は 1024 GiB、それ以外は `gib * 1073741824` を `uint64_t` に変換します（`include/strata/core/ple_residency.hpp:82-89`）。
- parser は `atof` のため、数値として解釈できない文字列は 0 として扱われ、負数と NaN は上記 validation で拒否されます。重複指定を拒否する処理はなく、引数走査で後に現れた値が `o.ram_keep` を上書きします（`src/program/generate.cpp:3293-3298,3657-3661`）。
- [環境変数 `STRATA_RAM_KEEP_GIB`](../../../envvars/STRATA_RAM_KEEP_GIB.md) は CLI 引数を渡せない呼び出し元向けの同等設定です。CLI でこの option を指定すると、値が `0` でも環境変数より優先されます。CLI 未指定なら、空でなく `atof(v) > 0` の環境値を使用します（`src/program/generate.cpp:3692-3697`）。

## 実行時の動作

通常の engine parser は `o.ram_keep` に値を保持します。初期化後、`--resident-budget-gib` または `--resident-experts` が設定した resident headroom を `W` 未満から引き上げます。ただし `STRATA_RESIDENT_HEADROOM_GIB` が数値として 0 以上なら、その環境値が優先されます（`src/program/generate.cpp:3647-3672,3692-3700`）。

expert arena を開く際には必要量に `W` を加えた値を空き RAM と比較します。プロセスの hard memory limit がある場合は、fallback が許可されていると `max(W, fallback headroom)` も limit 判定に加わります（`src/core/expert_source.cpp:5874-5889`; 計算式は `include/strata/core/ple_residency.hpp:93-106`）。

arena が RAM 不足で使えず、自動 fallback が有効な場合、エンジンは `--mmap-experts` 相当の file source に切り替えます。expert profile があり、既に resident CPU mode でなく、fallback を無効化していない場合は、空き RAM から headroom を引いた範囲で profile 上位 expert の RAM copy も試します（`src/program/generate.cpp:7072-7088,7321-7343`）。この fallback の headroom は既定で Windows 8 GiB、その他 4 GiB と `W` の大きい方です。`STRATA_RESIDENT_HEADROOM_GIB` が設定されていればその値を使います（`include/strata/core/ple_residency.hpp:91,108-116`）。

`STRATA_ARENA_RAM_FALLBACK=0` は自動切替を無効化します。また、明示的な `--ple-io ram` や `--shared-expert-arena` を使う場合も自動 fallback の対象外です（`src/core/ple_residency.hpp:65-72`; 呼び出し側は `src/program/generate.cpp:7072-7077`）。

## 適用条件と副作用

- この値は起動時の expert RAM 配置判定に使われ、実行中に再読込する処理は確認できません。expert arena と file/RAM-copy のどちらを使うかに影響します（`src/program/generate.cpp:3692-3700,7306-7317`）。
- 0 のときは arena の判定に追加 headroom を要求せず、RAM-copy fallback では platform の安全 headroom が適用されます（`src/program/generate.cpp:1288-1289`; `include/strata/core/ple_residency.hpp:79-81,108-112`）。
- arena が選ばれると `ArenaExpertSource` に値が渡り、`W` GiB を空けられる場合だけ arena を選ぶ判定になります。利用可能 RAM を取得できない環境での判定詳細は、この条件分岐からは確定できません（`src/core/expert_source.cpp:5874-5905`）。
- Qwen3.5 MoE モデルは通常 parser に入る前に `src/qwen35` の実装へ委譲されます。したがって、この文書が追った `src/program/generate.cpp` 側の option 動作はその実行経路には適用されません（`src/program/generate.cpp:3273-3283`）。

## 出力とエラー

`W > 0` の場合、expert arena を開く前に stderr へ arena の条件と RAM-copy fallback の headroom を説明する行を出します（`src/program/generate.cpp:7306-7315`）。RAM 不足で fallback に切り替えると、同じく stderr に arena 不足と file source への切替を通知します（`src/program/generate.cpp:7321-7327`）。arena が使えず fallback も許可されない場合や、後続の expert source を開けない場合は stderr に理由を出し、通常経路では終了コード 1 になります（`src/program/generate.cpp:7345-7347`; hard limit の拒否理由は `src/core/expert_source.cpp:5892-5899`）。

## 根拠

- option のヘルプ説明と既定値: `src/program/generate.cpp:1285-1289`。
- 値の parser、validation、変換と不足値処理: `src/program/generate.cpp:3293-3298,3657-3661`。
- GiB→byte 変換、1024 GiB 上限、headroom 計算: `include/strata/core/ple_residency.hpp:74-116`。
- 環境変数との優先順位と明示 resident mode への反映: `src/program/generate.cpp:3692-3700`。
- arena の RAM/hard limit 判定: `src/core/expert_source.cpp:5874-5905`。
- arena 不足時の file/RAM-copy fallback と通知: `src/program/generate.cpp:7072-7088,7321-7347`。
- Qwen3.5 MoE の別 parser への分岐: `src/program/generate.cpp:3273-3283`。
