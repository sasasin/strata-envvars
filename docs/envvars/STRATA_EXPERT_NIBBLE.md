# `STRATA_EXPERT_NIBBLE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

`1` を指定すると、対応する native expert pack の対象層について、GPU expert cache の gate/up 部分を 4-bit slot に変換し、その slot 用 CUDA kernel を使います。down rows とホスト上の GGUF pack はそのままです。対象になり得る format は既定で IQ2_S (22)、IQ3_XXS (18)、IQ3_S (21) ですが、各層の gate/up の形式・形状が条件を満たすものだけです。未設定または `0` では通常の GGUF slot を使います。設定値は生成開始時に読み、CLI 引数で有効化する機能ではありません。成功時には `--adapt-swaps` / `--peer-adapt-swaps` を 0 にします。`engine/include/strata/core/expert_nibble.hpp:50-60, 213-218, 238-269`、`engine/src/program/generate.cpp:5440-5480`。

この変数は Strata のエンジン実装が直接 `std::getenv` で読みます。ソース全体の完全一致検索では、実際の読み取りは `expert_nibble.hpp` の `config()` にある一箇所です。ほかの一致箇所はコメント、ログ、補助ツール名または資料で、別の読み取り経路ではありません。

## 値と判定

`config()` の関数内 `static const Config` が最初に呼ばれたときに値を保存します。文字列全体を `strcmp` で比較し、数値変換や前後空白の除去はしません。`1` だけが ON、`0` だけが明示的 OFF です。未設定と空文字も OFF です。それ以外の非空文字列は無効値となり、設定値を含むエラーを保存します。したがって `true`、`01`、`0anything`、` 1`、`1 `、`TRUE` は無効です。`engine/include/strata/core/expert_nibble.hpp:238-269`。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 全 build | OFF | `1`（完全一致） | 空文字は OFF。それ以外の非空値（例: `true`、`0anything`、`01`、空白付き `1`）は設定エラー。`0` は OFF |

無効値でも通常はプロセスを終了せず、対象機能をこの起動では OFF にして警告を出し、GGUF slot のまま起動を続けます。対象環境変数のエラーは `nib_asked` の判定にも使われるため、`1` 以外の無効値もこの警告経路に入ります。`engine/src/program/generate.cpp:5446-5461`。

## 有効になる条件

値が `1` でも、以下を満たさないと変換は有効になりません。

- **Build と GPU:** `STRATA_EXPERIMENTAL_SM60` を有効にした CUDA build で、`STRATA_NATIVE_EXPERTS` も定義されていること。HIP、Metal、またはその macro のない build では拒否理由を警告し、通常 slot に戻します。さらに実行時に見える CUDA device が 1 台以上あり、検査対象となる全 CUDA device が compute capability 6.0 である必要があります。`engine/include/strata/core/expert_nibble.hpp:33-38`、`engine/src/program/generate.cpp:3403-3424`。
- **モデルと対象層:** native pack が必要です。各変換層は既定形式または `STRATA_EXPERT_NIBBLE_FMTS` に列挙された形式で、`n_embd=2560`、`n_ff=640`、想定された gate/up/down の配置、NVFP4 tail なし、down 部分が 16-byte 単位という条件を満たす必要があります。`STRATA_EXPERT_NIBBLE_SKIP` に列挙した層は GGUF slot に残ります。候補層が一つもなければ警告して機能を OFF にします。`engine/include/strata/core/expert_nibble.hpp:250-265, 315-356`、`engine/src/program/generate.cpp:5451-5461`。
- **起動オプション:** `--peer-device`、`--expert-cache-device1..3` による remote expert cache、`--kv-grow`、`--vram-elastic` は GGUF slot を使うため同時利用できません。`--expert-profile` が空、または `--expert-cache 0` でも変換できません。`engine/src/program/generate.cpp:3425-3435`。
- **他の設定:** `STRATA_MMQ_DIRECT` は `atoi` の結果が非 0、`STRATA_PREFILL_MMQ` は `atoi` の結果が 0、`STRATA_PF_FUSED` と `STRATA_EXPERT_V2` は値の先頭文字が `1`、`STRATA_FS_SLOTS` は `atoi` の結果が正数、または `STRATA_EXP_MODE` は `atoi` の結果が 0/8 以外なら、prompt または expert 経路が GGUF slot と両立しないため警告して OFF にします。たとえば `STRATA_PREFILL_MMQ=abc` は `atoi` が 0 となるため拒否条件です。各判定の根拠は `engine/include/strata/core/expert_nibble.hpp:277-298` です。`engine/include/strata/core/expert_nibble.hpp:277-298`。
- **Prompt 経路:** 変換層すべてが prompt MMQ gather を使えなければなりません。MMQ がない層の FP16 dequant、WMMA tile、対応する fused kernel、または GGUF 行列配置と一致しない MMQ 行列があれば不適合です。`STRATA_MMQ_DIRECT` もここで拒否されます。`engine/src/prefill/prefill.cpp:3915-3938`。
- **常駐と chunk:** profile fill 後に、全層の全 expert がその層を実行する GPU の cache に常駐できなければ開始を拒否します。prompt path が cache slot を借りる場合や、機能 OFF 時と異なる prompt chunk が必要な場合も開始を拒否します。serve 経路の chunk 検査では、明示した `--prefill N` はその N を維持する必要があります。`engine/src/program/generate.cpp:9957-9989, 12812-12843, 23961-23965`。

## 実行時の詳細

`config()` は初回呼び出し時に対象値と関連する `STRATA_EXPERT_NIBBLE_RECHECK`、`STRATA_EXPERT_NIBBLE_FMTS`、`STRATA_EXPERT_NIBBLE_SKIP` をまとめて読み、静的に保持します。プロセス起動後に環境を変更しても再読込されません。エンジンは expert layout の読込後、GPU cache の slot 見積もり・確保より前に適用可否を検査します。理由があれば `set_layers({})` に戻し、理由がなければ層ごとの slot table を設定します。`engine/include/strata/core/expert_nibble.hpp:238-269, 345-369`、`engine/src/program/generate.cpp:5355-5368, 5440-5464`。

有効な場合、profile から cache を一度だけ埋めるとき、対象層の GGUF blob を CUDA 上で 4-bit slot に変換します。変換時に各 item の再 decode 比較と、slot から再構築した GGUF block と元 blob の比較を行い、slot hash を記録します。profile fill と検証に失敗した場合は stderr に理由を出して `generate` を終了コード 1 で返します。layer split では stage ごとに同じ fill を行います。成功後は全 expert の VRAM 常駐を確認して cache を seal し、slot の書き換えを防ぎます。`engine/src/program/generate.cpp:3162-3273, 3290-3314, 9671-9763, 9882-9931, 9957-9989`。

`STRATA_EXPERT_NIBBLE_RECHECK=1` は別の補助スイッチで、serve では各完了 request の後に全変換 slot の hash をロード時の値と比較します。不一致理由を stderr に出し、layer が特定できる場合は `nib::fatal` が `abort()` します。これは対象変数自体の値の再読込ではありません。`engine/include/strata/core/expert_nibble.hpp:247-248, 394-400`、`engine/src/program/generate.cpp:23305-23324`。

## ログと測定値

適用条件を満たさないときは stderr に次の形式で警告し、GGUF slot で続行します（`%s` は実際の拒否理由）。

```text
strata generate: WARNING: STRATA_EXPERT_NIBBLE is off for this start: %s; the expert slots stay GGUF blocks
```

有効時は変換層数・format 別内訳・追加 VRAM 量・adaptive tier を無効化したことを stderr に表示します。fill の確保・変換・検証失敗は理由付き stderr の後に終了コード 1 となり、常駐不足や prompt 条件不適合もそれぞれ理由を stderr に出して終了コード 1 となります。`engine/src/program/generate.cpp:5457-5480, 9700-9705, 9732-9763, 9976-9989, 12837-12843`。

不正な slot を GGUF block として扱う経路に到達した場合の最終防護は `stderr` に `strata: STRATA_EXPERT_NIBBLE: layer ... reached ... - stopping` を出して `abort()` します。`engine/include/strata/core/expert_nibble.hpp:394-400`。

`docs/OLDER_GPUS.md:200-231` の適用条件・必要な常駐・prompt 制約は上記の実装と概ね一致します。実装では事前の互換性不足は警告して機能を OFF にし、profile fill 中の round-trip / GGUF 比較不一致は理由を stderr に出して終了コード 1 を返します。資料記載の性能値はここでは再測定・一般化していません。

## 根拠

- 値の読み取り、cache、関連変数: `engine/include/strata/core/expert_nibble.hpp:211-298`
- Build、GPU、CLI 条件と拒否理由: `engine/src/program/generate.cpp:3400-3437`
- 層ごとの形式・形状判定と slot table: `engine/include/strata/core/expert_nibble.hpp:315-356`
- prompt 経路の適合確認: `engine/src/prefill/prefill.cpp:3915-3938`
- 変換、比較、read-back と異常経路: `engine/src/program/generate.cpp:3162-3348, 9671-9763, 9882-9931`
- 常駐、serve の prompt 制約、hash 再検査: `engine/src/program/generate.cpp:9957-9989, 12812-12843, 23305-23324`
