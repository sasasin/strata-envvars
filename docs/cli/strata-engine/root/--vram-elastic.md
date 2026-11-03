# `--vram-elastic`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--vram-elastic` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

serve 用の expert cache を単一の `cudaMalloc` 領域ではなく CUDA 仮想メモリ管理 (VMM) の物理セグメントで構成します。これにより、サーバーが明示的に受け取る `VRAM [reserve_mib]` コマンドに応じて、リクエスト間に cache の末尾を解放し、空き VRAM を他のプログラムへ譲ったり、後でセグメントを再割当てしたりできます。フラグを付けただけでは VRAM は自動調整されません（`src/program/generate.cpp:794-797,1112-1114,13447-13454`）。

## 使い方

```sh
strata --native MODEL.gguf --serve --expert-cache auto --expert-profile PROFILE --vram-elastic
```

これは既存の native GGUF、expert profile を使う serve 起動の例です。起動後の `VRAM` コマンドはサーバー制御プロトコルの入力であり、このフラグ自体に reserve 値を渡す構文ではありません（`src/program/generate.cpp:1112-1114,13471-13478`）。

## 値と既定値

- `--vram-elastic` は値なしの boolean option で、未指定時は `false`（無効）です。別名はありません（`src/program/generate.cpp:794-797,3481`）。
- セグメント幅は別 option `--vram-segment-mib N` で指定し、既定値は 512 MiB です。parser は `atoll` で値を読み、専用の数値 validation は行いません。ただし幅が 64 MiB 未満なら `--vram-elastic` は無効化されます（`src/program/generate.cpp:797,3481-3483,7841-7855`）。
- `--vram-elastic` の重複指定に特別な処理はなく、同じ真偽値を再設定します。値を続けて指定する option ではありません（`src/program/generate.cpp:3481-3483`）。

## 実行時の動作

有効条件を満たす場合、`--vram-segment-mib` をバイトへ変換して expert cache に設定し、cache の初期化時に要求容量分の仮想アドレス範囲を予約します。CUDA の推奨割当粒度に合わせてセグメント幅と総容量を切り上げ、起動時には各セグメントを物理確保して範囲へ map します（`src/program/generate.cpp:7841-7855,7913-7922`; `src/core/expert_cache.cpp:397-444`）。

serve 中に `VRAM` を単独で受け取ると起動時の `--vram-reserve-mib` 値を使い、`VRAM N` では N MiB を空ける目標にします。現在の空き容量が目標未満なら末尾の cache セグメントを unmap/release し、該当 expert を cache 外扱いにします。目標より余裕がある場合はセグメントを再 map し、追い出した expert を slot に再充填します。prompt 用 slot の貸出が残る場合は処理を拒否し、変更後は prompt chunk を残存 cache に合わせます（`src/program/generate.cpp:13447-13470,13471-13552`; `src/core/expert_cache.cpp:484-514,518-545`）。

## 適用条件と副作用

- この機能は serve と単一 GPU の組み合わせに限定されます。layer split、helper GPU 上の remote expert cache、`--vram-segment-mib < 64`、HIP build では起動時に stderr へ `--vram-elastic is off: ...` を出して無効化し、通常の cache 確保を続けます（`src/program/generate.cpp:7839-7855`）。
- GPU/driver が CUDA VMM を提供しない場合、expert cache 初期化時に警告を stderr へ出して segmented mode を off にし、単一ブロックの cache に切り替えます。セグメント確保や map が失敗した場合は cache open が失敗し、通常の起動失敗経路に入ります（`src/core/expert_cache.cpp:386-444,607-635`; `src/program/generate.cpp:7913-7945`）。
- expert cache 自体が無効（既定の `--expert-cache 0`）なら、この設定の実用上の対象となる cache はありません（`src/program/generate.cpp:731-739,7841-7855`）。
- `VRAM` 制御は resident low-RAM mode、`--peer-device`、prompt loan 中、batch slot の decode 中には拒否されます。また、縮小で cache にいた expert は cache miss となり、拡張時には slot の再充填が行われます（`src/program/generate.cpp:13481-13493,14772-14778`）。
- `VRAM` command は数値なしなら起動時 reserve を使い、負数や数値のない引数は `expected: VRAM [reserve_mib]` エラーになります。確認できた範囲では正の値に上限を設ける validation はなく、メモリ状況や prompt 用 cache floor により要求値どおりの空き容量にならない場合があります（`src/program/generate.cpp:13471-13510`）。

## 出力とエラー

- 制御が成功すると stderr に解放目標、cache slot の変化、実空き容量、prompt chunk を記録し、stdout に `VRAM reserve_mib=...` の状態行を出します（`src/program/generate.cpp:13552-13564`）。
- 制御拒否や処理失敗は serve protocol の stdout に `ERR ...` として出力されます（`src/program/generate.cpp:14772-14778`）。再 map 不可時は cache の現在サイズを更新して警告注記を付けて応答を続ける経路があり、再充填・同期の失敗は `VRAM: refilling the cache failed` 等のエラーになります（`src/program/generate.cpp:13518-13550`; `src/core/expert_cache.cpp:518-545`）。

## 調査範囲

現行 checkout の parser、起動時の適用条件、expert cache の VMM 確保/縮小/拡張、および serve の `VRAM` 入力処理を確認しました。実 GPU/driver ごとの VMM 対応、実際の空き VRAM 推移、性能差は実機実行や測定を行っていないため確認していません。CLI `--help` の実行および Release binary の照合も行っていません。

## 根拠

- `src/program/generate.cpp:794-797,1112-1114,3481-3483` — option の既定値、help 記述、parser。
- `src/program/generate.cpp:7839-7855,7913-7945` — 適用条件、cache への設定、初期化失敗経路。
- `src/core/expert_cache.cpp:386-444,484-514,518-545,607-640` — CUDA VMM 対応判定、セグメント map/unmap、fallback、確保エラー。
- `src/program/generate.cpp:13447-13564,14772-14778` — VRAM reserve 制御、slot の縮小/復元、出力とエラー応答。
