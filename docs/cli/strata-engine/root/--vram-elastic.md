# `strata --vram-elastic`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジンの root 引数） |
| オプション | `--vram-elastic` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--serve` で動かすエンジンの expert cache を物理 VRAM セグメントに分け、サーバーの `VRAM <reserve_mib>` 制御で要求間に cache の末尾を解放し、空き VRAM を他のプログラムへ返せるようにします。空きが増えたときはセグメントを再確保して cache を戻します。通常は単一の `cudaMalloc` で cache を確保するため、この機能は opt-in です（`engine/src/program/generate.cpp:962-965, 1312-1314`、`engine/include/strata/core/expert_cache.hpp:119-126`）。

## 使い方

```sh
# CUDA/NVIDIA 環境で、serve モードのエンジンに有効化する
strata --serve --vram-elastic --native /path/to/model-shard.gguf

# セグメントを既定の 512 MiB から 256 MiB にする
strata --serve --vram-elastic --vram-segment-mib 256 --native /path/to/model-shard.gguf
```

`--native` の値は利用するモデル shard のパスに置き換えます。エンジンの parser は `--vram-elastic` を真偽値として読み取り、モデル別の別 parser に振り分けられた場合はこの文書の対象外です（`engine/src/program/generate.cpp:3799-3813, 4031-4032`）。

## 値と既定値

- `--vram-elastic` 自体は値を取りません。省略時は `false` で、セグメント化されない通常の cache になります（`engine/src/program/generate.cpp:962-965, 4031`）。
- セグメントサイズは関連する `--vram-segment-mib` で MiB 単位に指定し、省略時は 512 MiB です。値は `atoll` で整数化され、明示的な数値形式検証はこの parser 箇所にはありません（`engine/src/program/generate.cpp:965, 4032`）。
- セグメントサイズが 64 MiB 未満（数値化できない値を含む）なら起動時に `--vram-elastic is off: --vram-segment-mib is below 64` を stderr に出し、フラグを無効化します。64 MiB 以上の上限値チェックは確認できません（`engine/src/program/generate.cpp:9505-9518`）。

## 実行時の動作

有効条件を満たすと、cache を開く前に segment bytes を設定し、expert cache を通常の単一 allocation ではなく、固定仮想アドレス範囲と物理セグメントで構成します。セグメントのサイズは CUDA driver の推奨 allocation granularity に切り上げられます（`engine/src/program/generate.cpp:9502-9518, 9861-9866`、`engine/src/core/expert_cache.cpp:421-449`）。

実行中にサーバーが `VRAM <reserve_mib>` を処理すると、指定した空き容量に合わせて cache を縮小・拡張します。縮小では cache の末尾を解放し、その領域にあった expert slot を退避するため CPU 側の miss になります。拡張時は slot を再充填し、prompt 用の cache loan も現在の容量に合わせ直します。この変更は要求間にサーバーの VRAM 制御を受けた場合だけ行われ、自動では起きません（`engine/src/program/generate.cpp:16433-16440, 16486-16518, 16543-16560, 16561-16596`）。

## 適用条件と副作用

- `--serve` が必要です。serve 外、他 GPU 上の helper cache（`expert_cache_remote` に正の値がある場合）、または segment が 64 MiB 未満なら stderr に理由を出してフラグを無効化し、起動は通常 cache 経路で続きます（`engine/src/program/generate.cpp:9505-9518`）。
- HIP build では NVIDIA 専用として無効化されます。CUDA でも GPU/driver が virtual memory management を提供しない場合、cache open 時に stderr へ通知して単一ブロックの cache に戻ります。この場合 `VRAM` 制御は segmented cache を必要とするエラーになります（`engine/src/program/generate.cpp:9510-9518`、`engine/src/core/expert_cache.cpp:404-429, 641-649`、`engine/src/program/generate.cpp:16506-16508`）。
- layer split では各 stage の cache にも同じ segment サイズを設定します（`engine/src/program/generate.cpp:9861-9866`）。一方、resident low-RAM mode や `--peer-device` 使用中は VRAM 制御コマンドが拒否されます（`engine/src/program/generate.cpp:16510-16516`）。
- VMM のアドレス予約、セグメント確保、mapping が失敗すると segmented cache の open が失敗します。通常の非対応 fallback と異なり、これらの資源確保エラーは cache open の失敗経路に進みます（`engine/src/core/expert_cache.cpp:431-464, 648-649`）。

## 出力とエラー

- エンジン起動時の `INFO` 行には、実際の cache が segmented かを `vram_elastic=0|1` で出します。指定が有効でも GPU/driver 非対応時は `0` になり得ます（`engine/src/program/generate.cpp:16098-16116`）。
- VRAM 制御が segmented cache なしで呼ばれた場合は `VRAM needs an engine started with --vram-elastic (NVIDIA GPU, --serve)` を、prompt loan が使用中なら loan 解放待ちのエラーを返します。VRAM 制御成功時は設定を stderr と stdout に出力します（`engine/src/program/generate.cpp:16506-16520, 16619-16634`）。
- cache の segmented allocation が失敗した場合は、起動時 cache open のエラー処理へ進みます。個々のエラー文字列は VMM 操作箇所で設定されます（`engine/src/core/expert_cache.cpp:431-464`）。

## 根拠

- `engine/src/program/generate.cpp:962-965, 1312-1314, 4031-4032` — 既定値、help 表示、parser。
- `engine/src/program/generate.cpp:9502-9518, 9861-9866` — 有効条件と cache への設定。
- `engine/src/core/expert_cache.cpp:415-464, 641-675` — CUDA VMM segmented allocation、非対応時 fallback、確保失敗。
- `engine/include/strata/core/expert_cache.hpp:119-140` — segmented cache が固定アドレスを維持する設計と segment 情報。
- `engine/src/program/generate.cpp:16433-16440, 16486-16518, 16543-16596, 16619-16634` — VRAM 制御時の縮小・拡張、前提条件、出力。
- `engine/src/program/generate.cpp:16098-16116` — 実際の segmented 状態を示す `INFO` 出力。

調査範囲は上記 checkout の `generate.cpp` parser とその cache 実装です。GPU 実機・driver ごとの VMM 対応状況や確保成功性は実行していないため、この文書では保証していません。
